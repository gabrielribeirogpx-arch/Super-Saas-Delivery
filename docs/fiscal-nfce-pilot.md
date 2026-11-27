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
