#!/usr/bin/env bash
# ==============================================================================
# Provisionamento enxuto na Azure (brazilsouth) para o Challenge 2 Berkanan
# Topologia híbrida (ADR-009 proposto):
#   1. VM Linux Standard_B2als_v2 (2 vCPU AMD EPYC, 4 GB RAM + swap 4 GB, StandardSSD_LRS 64 GB) + Docker + Caddy HTTPS
#      (Se a Azure Policy estudantil bloquear brazilsouth, use LOCATION=northcentralus como no Challenge 1.)
#   2. Domínio gratuito dedicado (ex.: berkanan-challenge-2.duckdns.org) apontando para o IP estático da VM
#   3. Azure Static Web Apps (Free) para o frontend React Mobile First
#
# Segurança e FinOps (Azure for Students) por padrão:
#   - Executa em modo --dry-run enquanto CONFIRM_PROVISION!=1 e --apply não for passado.
#   - EXIGE ADMIN_CIDR restrito (ex.: SEU_IP/32); falha imediatamente se ausente ou aberto (0.0.0.0/0).
#   - Libera apenas 80/443 (público) e 22 (restrito a ADMIN_CIDR); bloqueia 5432/8000/8001.
#   - Configura auto-shutdown diário às 23:00 BRT (02:00 UTC) para proteger créditos.
# ==============================================================================

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-berkanan-staging}"
LOCATION="${LOCATION:-brazilsouth}"
VM_NAME="${VM_NAME:-vm-berkanan-api}"
VM_SIZE="${VM_SIZE:-Standard_B2als_v2}"
VM_IMAGE="${VM_IMAGE:-Ubuntu2404}"
STORAGE_SKU="${STORAGE_SKU:-StandardSSD_LRS}"
AUTO_SHUTDOWN_TIME_UTC="${AUTO_SHUTDOWN_TIME_UTC:-0200}"
ADMIN_USER="${ADMIN_USER:-azureuser}"
DNS_LABEL="${DNS_LABEL:-berkanan-api}"
API_DOMAIN="${API_DOMAIN:-berkanan-challenge-2.duckdns.org}"
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

if [[ -z "${ADMIN_CIDR}" || "${ADMIN_CIDR}" == "*" || "${ADMIN_CIDR}" == "Internet" || "${ADMIN_CIDR}" == "0.0.0.0/0" || "${ADMIN_CIDR}" == "::/0" ]]; then
  echo "[ERRO] ADMIN_CIDR obrigatório e restrito (ex.: ADMIN_CIDR=\"203.0.113.10/32\"). A porta 22 nunca pode ficar aberta para a internet." >&2
  exit 1
fi

if [[ ! "${ADMIN_CIDR}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}/([1-9]|[12][0-9]|3[0-2])$ ]]; then
  echo "[ERRO] ADMIN_CIDR inválido: '${ADMIN_CIDR}'. Use formato CIDR IPv4 restrito (ex.: SEU_IP/32)." >&2
  exit 1
fi

run_az() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[DRY-RUN] %s\n' "$*"
  else
    "$@"
  fi
}

echo "=== Provisionamento Azure (${LOCATION}) | Grupo: ${RESOURCE_GROUP} | SKU: ${VM_SIZE} (${STORAGE_SKU}) ==="

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
  --source-address-prefixes "${ADMIN_CIDR}" \
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
  --storage-sku "${STORAGE_SKU}" \
  --os-disk-delete-option Delete \
  --nic-delete-option Delete \
  --authentication-type ssh \
  --admin-username "${ADMIN_USER}" \
  --generate-ssh-keys \
  --nsg "${NSG_NAME}" \
  --public-ip-sku Standard \
  --public-ip-address-allocation Static \
  --public-ip-address-dns-name "${DNS_LABEL}"

# FinOps: desliga/desaloca automaticamente todos os dias às 23:00 BRT (02:00 UTC)
run_az az vm auto-shutdown \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${VM_NAME}" \
  --time "${AUTO_SHUTDOWN_TIME_UTC}"

echo ""
echo "=== Próximo passo: Azure Static Web Apps (Free) para o frontend React (quando entregue por R5) ==="
run_az az staticwebapp create \
  --name "${SWA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --location "${SWA_LOCATION}" \
  --sku Free

echo ""
echo "Aponte o registro A de ${API_DOMAIN} (ex.: DuckDNS gratuito) para o IP público estático da VM."
echo "Economia diária manual: az vm deallocate -g ${RESOURCE_GROUP} -n ${VM_NAME}"
echo "Teardown pós-07/12 (após pg_dump): az group delete --name ${RESOURCE_GROUP} --yes"
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[INFO] Execução em modo --dry-run. Para aplicar de fato, rode: ADMIN_CIDR=\"SEU_IP/32\" bash $0 --apply"
fi
