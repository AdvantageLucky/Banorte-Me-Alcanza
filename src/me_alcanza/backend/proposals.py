import time
import uuid
from dataclasses import dataclass, field

PROPOSAL_TTL_SECONDS = 300


@dataclass
class Proposal:
    id: str
    account_id: str
    tipo: str
    payload: dict
    resumen: str
    created_at: float = field(default_factory=time.time)


PROPOSALS: dict[str, Proposal] = {}


def crear_propuesta(account_id: str, tipo: str, payload: dict, resumen: str) -> Proposal:
    proposal = Proposal(
        id=str(uuid.uuid4()),
        account_id=account_id,
        tipo=tipo,
        payload=payload,
        resumen=resumen,
    )
    PROPOSALS[proposal.id] = proposal
    return proposal


def obtener_propuesta_valida(proposal_id: str, account_id: str) -> Proposal | None:
    proposal = PROPOSALS.get(proposal_id)
    if proposal is None or proposal.account_id != account_id:
        return None
    if time.time() - proposal.created_at > PROPOSAL_TTL_SECONDS:
        PROPOSALS.pop(proposal_id, None)
        return None
    return proposal


def descartar_propuesta(proposal_id: str) -> None:
    PROPOSALS.pop(proposal_id, None)
