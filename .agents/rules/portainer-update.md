# Regra de Atualização do Portainer

Conforme solicitado pelo usuário, as seguintes diretrizes devem ser estritamente seguidas ao realizar alterações neste projeto:

1. **Deploy Automático no Portainer:**
   Toda vez que você (assistente) fizer um *commit* e um *push* de código para o Git que atualize o sistema principal, você deve:
   - Aguardar a conclusão do GitHub Actions (ou qualquer CI configurado) garantindo que a nova imagem Docker foi "buildada" e enviada para o registro.
   - Logo em seguida, você deve providenciar a atualização da stack `grafica` no Portainer (id=5), forçando um "Pull Image" (baixar a imagem mais recente) e realizando o "Prune" dos containers antigos.

2. **Limitação de Firewall (Cloudflare):**
   *Atenção:* Ocasionalmente o Cloudflare pode bloquear requisições HTTP locais (`PUT` para a API do Portainer) com o erro `1010 (Access Denied)`. Caso isso ocorra, o assistente deve avisar o usuário imediatamente ou buscar alternativas para aprovar ou aplicar a atualização via interface Web do Portainer ou Webhook seguro.
