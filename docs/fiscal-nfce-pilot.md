# Piloto de NFC-e com a Focus NFe

Cadastre o emitente em **Minha Loja → Fiscal** na base de teste. Na Focus, habilite o mesmo CNPJ para NFC-e em homologação e configure o certificado e o CSC conforme a UF. Use um pedido de mesa concluído em dinheiro sem descontos, troco ou adicionais. O piloto aceita Simples Nacional (CRT 1).

Configure `FOCUS_NFCE_PILOT_TENANT_ID` com o ID da loja, `FOCUS_NFCE_PILOT_NAMESPACE` com um identificador alfanumérico estável e exclusivo da base de teste (até 20 caracteres) e `FOCUS_NFCE_HOMOLOGATION_TOKEN` com o token do emitente via gerenciador de segredos. A prévia pode ser gerada sem token.

Prepare um JSON por ID de produto. Este exemplo mostra o formato. Preencha com os códigos aprovados pela contabilidade para os produtos do teste.

```json
{
  "7": {
    "codigo_ncm": "19059090",
    "cfop": "5102",
    "icms_origem": "0",
    "icms_situacao_tributaria": "102",
    "pis_situacao_tributaria": "07",
    "cofins_situacao_tributaria": "07",
    "unidade_comercial": "UN"
  }
}
```

Na raiz do backend, gere a prévia e depois envie para homologação.

```bash
python -m scripts.run_focus_nfce_pilot 123 produtos-fiscais.json
python -m scripts.run_focus_nfce_pilot 123 produtos-fiscais.json --submit
```

O envio consulta a Focus pela referência antes de transmitir. Após uma falha de comunicação, repita com o mesmo pedido e namespace para recuperar o resultado. Se a nota for autorizada, a saída inclui a chave e os caminhos do XML e DANFE que a Focus retornar. Em caso de rejeição registrada, consulte a referência no portal da Focus.

[Operações da API de NFC-e](https://doc.focusnfe.com.br/docs/nfce-operacoes-disponiveis-na-api)

## Piloto pelo painel

Configure o segredo `FOCUS_NFE_MASTER_TOKEN` no backend e mantenha um
`FOCUS_NFCE_PILOT_NAMESPACE` estável e exclusivo para o banco que executa
o piloto. O painel fica em **Minha Loja → Fiscal** para donos e administradores.

1. Salve os dados fiscais do emitente, preencha o endereço e anexe o A1. Informe
   o CSC e seu identificador de homologação quando exigidos pela UF.
2. Clique em **Conectar emissão fiscal**. A API de Empresas usa a URL
   administrativa da Focus e cria um cadastro real de emitente. O sistema
   guarda o identificador do emitente e recupera o token de homologação pela
   API. O A1, sua senha e o CSC são encaminhados à Focus, sem gravação no
   banco do Fomizero.
3. Informe o ID interno do pedido de teste e os códigos fiscais de seus
   produtos. Clique em **Emitir ou consultar NFC-e de teste**. A emissão só
   usa o endereço de homologação e a referência é estável por pedido.

Para um CNPJ já cadastrado manualmente na conta Focus, o painel interrompe o
cadastro e informa que precisa de vinculação assistida. O fluxo atual de CLI
continua disponível para testar esse emitente com o token de homologação.
