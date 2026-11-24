#!/usr/bin/env bash
# ==============================================================================
# Provisionamento enxuto na Azure (brazilsouth) para o Challenge 2 Berkanan
# Topologia híbrida (ADR-009 proposto):
#   1. VM Linux Standard_B2ms (2 vCPU, 8 GB RAM, SSD local) + Docker + Caddy HTTPS
#   2. Azure Static Web Apps (Free) para o frontend React Mobile First
#
# Segurança por padrão:
#   - Executa em modo --dry-run enquanto CONFIRM_PROVISION!=1 e --apply não for passado.
#   - Libera apenas 80/443 (público) e 22 (restrito a ADMIN_CIDR); bloqueia 5432/8000/8001.
# ==============================================================================

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-berkanan-staging}"
LOCATION="${LOCATION:-brazilsouth}"
VM_NAME="${VM_NAME:-vm-berkanan-api}"
VM_SIZE="${VM_SIZE:-Standard_B2ms}"
VM_IMAGE="${VM_IMAGE:-Ubuntu2404}"
ADMIN_USER="${ADMIN_USER:-azureuser}"
DNS_LABEL="${DNS_LABEL:-berkanan-api}"
NSG_NAME="${NSG_NAME:-nsg-berkanan-api}"
ADMIN_CIDR="${ADMIN_CIDR:-}"
SWA_NAME="${SWA_NAME:-swa-berkanan-web}"
SWA_LOCATION="${SWA_LOCATION:-eastus2}"
DRY_RUN=1

for arg in "$@"; do
  case "${arg}" in
    --apply)
      DRY_RUN=0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    *)
      echo "[ERRO] Argumento desconhecido: ${arg}. Use --dry-run ou --apply." >&2
      exit 1
      ;;
  esac
done

if [[ "${CONFIRM_PROVISION:-0}" == "1" ]]; then
  DRY_RUN=0
fi

run_az() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[DRY-RUN] %s\n' "$*"
  else
    "$@"
  fi
}

if [[ -z "${ADMIN_CIDR}" ]]; then
  echo "[AVISO] ADMIN_CIDR não definido. Defina ADMIN_CIDR=\"SEU_IP/32\" para restringir o SSH (porta 22)." >&2
  SSH_SOURCE_PREFIX="Internet"
else
  SSH_SOURCE_PREFIX="${ADMIN_CIDR}"
fi

echo "=== Provisionamento Azure (${LOCATION}) | Grupo: ${RESOURCE_GROUP} ==="

run_az az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}"

run_az az network nsg create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${NSG_NAME}" \
  --location "${LOCATION}"

run_az az network nsg rule create \
  --resource-group "${RESOURCE_GROUP}" \
  --nsg-name "${NSG_NAME}" \
  --name AllowHTTP \
  --priority 100 \
  --direction Inbound \
  --access Allow \
  --protocol Tcp \
  --destination-port-ranges 80

run_az az network nsg rule create \
  --resource-group "${RESOURCE_GROUP}" \
  --nsg-name "${NSG_NAME}" \
  --name AllowHTTPS \
  --priority 110 \
  --direction Inbound \
  --access Allow \
  --protocol Tcp \
  --destination-port-ranges 443

run_az az network nsg rule create \
  --resource-group "${RESOURCE_GROUP}" \
  --nsg-name "${NSG_NAME}" \
  --name AllowSSHAdmin \
  --priority 120 \
  --direction Inbound \
  --access Allow \
  --protocol Tcp \
  --source-address-prefixes "${SSH_SOURCE_PREFIX}" \
  --destination-port-ranges 22

# Defesa em profundidade: bloqueio explícito das portas internas de banco/API
run_az az network nsg rule create \
  --resource-group "${RESOURCE_GROUP}" \
  --nsg-name "${NSG_NAME}" \
  --name DenyInternalPorts \
  --priority 200 \
  --direction Inbound \
  --access Deny \
  --protocol Tcp \
  --destination-port-ranges 5432 8000 8001

run_az az vm create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${VM_NAME}" \
  --location "${LOCATION}" \
  --image "${VM_IMAGE}" \
  --size "${VM_SIZE}" \
  --os-disk-size-gb 64 \
  --storage-sku Premium_LRS \
  --admin-username "${ADMIN_USER}" \
  --generate-ssh-keys \
  --nsg "${NSG_NAME}" \
  --public-ip-sku Standard \
  --public-ip-address-allocation Static \
  --public-ip-address-dns-name "${DNS_LABEL}"

echo ""
echo "=== Próximo passo: Azure Static Web Apps (Free) para o frontend React (quando entregue por R5) ==="
run_az az staticwebapp create \
  --name "${SWA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --location "${SWA_LOCATION}" \
  --sku Free

echo ""
echo "FQDN previsto da API: https://${DNS_LABEL}.${LOCATION}.cloudapp.azure.com"
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[INFO] Execução em modo --dry-run. Para aplicar de fato, rode: ADMIN_CIDR=\"SEU_IP/32\" bash $0 --apply"
fi
