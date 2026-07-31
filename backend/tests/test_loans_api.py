import pytest
from httpx import AsyncClient


def _loan_payload(**overrides):
    payload = {
        "name": "Financiamento Apto",
        "currency": "BRL",
        "principal_amount": 120000,
        "interest_rate": 0.01,
        "rate_period": "monthly",
        "amortization_system": "sac",
        "term_months": 12,
        "start_date": "2026-08-10",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_and_list_loans(client: AsyncClient, auth_headers):
    response = await client.post("/api/loans", json=_loan_payload(), headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["details"]["name"] == "Financiamento Apto"
    assert data["installments_total"] == 12

    response = await client.get("/api/loans", headers=auth_headers)
    assert response.status_code == 200
    loans = response.json()
    assert len(loans) == 1
    assert loans[0]["details"]["name"] == "Financiamento Apto"


@pytest.mark.asyncio
async def test_get_loan_not_found(client: AsyncClient, auth_headers):
    import uuid
    response = await client.get(f"/api/loans/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_installment_paid_and_unpaid_via_api(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/loans", json=_loan_payload(), headers=auth_headers)
    loan_id = create_resp.json()["details"]["id"]

    installments_resp = await client.get(f"/api/loans/{loan_id}/installments", headers=auth_headers)
    assert installments_resp.status_code == 200
    installments = installments_resp.json()
    assert len(installments) == 12
    first_id = installments[0]["id"]
    assert installments[0]["status"] == "projected"

    # Mark the first installment as paid.
    mark_resp = await client.patch(
        f"/api/loans/{loan_id}/installments/{first_id}",
        json={"status": "paid", "paid_date": "2026-08-12"},
        headers=auth_headers,
    )
    assert mark_resp.status_code == 200
    marked = mark_resp.json()
    assert marked["status"] == "paid"
    assert marked["paid_date"] == "2026-08-12"

    # The change is actually persisted, not just echoed back.
    refetch_resp = await client.get(f"/api/loans/{loan_id}/installments", headers=auth_headers)
    refetched = refetch_resp.json()
    assert refetched[0]["status"] == "paid"
    assert refetched[0]["paid_date"] == "2026-08-12"

    # The loan summary reflects the paid count too.
    summary_resp = await client.get(f"/api/loans/{loan_id}", headers=auth_headers)
    summary = summary_resp.json()
    assert summary["installments_paid"] == 1
    assert summary["next_installment"]["installment_number"] == 2

    # Unmark it — status flips back and paid_date/transaction_id clear.
    unmark_resp = await client.patch(
        f"/api/loans/{loan_id}/installments/{first_id}",
        json={"status": "projected", "paid_date": None},
        headers=auth_headers,
    )
    assert unmark_resp.status_code == 200
    unmarked = unmark_resp.json()
    assert unmarked["status"] == "projected"
    assert unmarked["paid_date"] is None
    assert unmarked["transaction_id"] is None

    summary_resp2 = await client.get(f"/api/loans/{loan_id}", headers=auth_headers)
    assert summary_resp2.json()["installments_paid"] == 0


@pytest.mark.asyncio
async def test_mark_installment_not_found(client: AsyncClient, auth_headers):
    import uuid
    create_resp = await client.post("/api/loans", json=_loan_payload(), headers=auth_headers)
    loan_id = create_resp.json()["details"]["id"]
    response = await client.patch(
        f"/api/loans/{loan_id}/installments/{uuid.uuid4()}",
        json={"status": "paid"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_loan_via_api_regenerates_schedule(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/loans", json=_loan_payload(term_months=6), headers=auth_headers)
    loan_id = create_resp.json()["details"]["id"]
    assert create_resp.json()["installments_total"] == 6

    update_resp = await client.put(
        f"/api/loans/{loan_id}", json=_loan_payload(term_months=10), headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["installments_total"] == 10


@pytest.mark.asyncio
async def test_delete_loan_via_api(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/loans", json=_loan_payload(), headers=auth_headers)
    loan_id = create_resp.json()["details"]["id"]

    delete_resp = await client.delete(f"/api/loans/{loan_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/loans/{loan_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_loans_rejected(client: AsyncClient, clean_db):
    response = await client.get("/api/loans")
    assert response.status_code == 401
