"""Focus company provisioning and lookup with server-side credentials."""

from hmac import compare_digest

import httpx

COMPANIES_URL = "https://api.focusnfe.com.br/v2/empresas"


class CompanyAlreadyRegistered(ValueError):
    pass


def list_companies(client: httpx.Client, master_token: str, cnpj: str) -> list:
    response = client.get(COMPANIES_URL, auth=(master_token, ""), params={"cnpj": cnpj})
    response.raise_for_status()
    companies = response.json()
    if not isinstance(companies, list):
        raise ValueError("Resposta inválida da consulta de empresas na Focus.")
    return companies


def create_company(client: httpx.Client, master_token: str, payload: dict) -> int:
    if list_companies(client, master_token, payload["cnpj"]):
        raise CompanyAlreadyRegistered
    response = client.post(COMPANIES_URL, auth=(master_token, ""), json=payload)
    response.raise_for_status()
    company = response.json()
    if (
        not isinstance(company, dict)
        or company.get("cnpj") != payload["cnpj"]
        or type(company.get("id")) is not int
        or company["id"] <= 0
    ):
        raise ValueError("Resposta de cadastro da Focus incompatível com o emitente.")
    return company["id"]


def get_homologation_token(client: httpx.Client, master_token: str, company_id: int, cnpj: str) -> str:
    for company in list_companies(client, master_token, cnpj):
        if isinstance(company, dict) and company.get("id") == company_id and company.get("cnpj") == cnpj:
            token = company.get("token_homologacao")
            if isinstance(token, str) and token.strip():
                return token.strip()
    raise ValueError("O token de homologação do emitente vinculado não está disponível.")


def verify_existing_company(client: httpx.Client, master_token: str, cnpj: str, proof: str) -> int:
    for company in list_companies(client, master_token, cnpj):
        if not isinstance(company, dict) or company.get("cnpj") != cnpj:
            continue
        company_id = company.get("id")
        token = company.get("token_homologacao")
        if (
            type(company_id) is int and company_id > 0
            and isinstance(token, str) and token
            and compare_digest(token.encode(), proof.encode())
        ):
            return company_id
    raise ValueError("Emitente ou token de homologação incompatível com o CNPJ da loja.")
