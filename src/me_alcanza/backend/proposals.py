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
    # Hilo donde el modelo la propuso (None solo si se creó fuera de un chat,
    # lo cual hoy no ocurre para ningún tipo de propuesta). Al confirmar, el
    # resultado se persiste en ESTE hilo — ver Orchestrator.confirm_action —
    # para que reabrir la conversación después muestre si de verdad se
    # autorizó, no solo la tarjeta original sin confirmar.
    conversacion_id: int | None = None


PROPOSALS: dict[str, Proposal] = {}


def crear_propuesta(
    account_id: str,
    tipo: str,
    payload: dict,
    resumen: str,
    conversacion_id: int | None = None,
) -> Proposal:
    proposal = Proposal(
        id=str(uuid.uuid4()),
        account_id=account_id,
        tipo=tipo,
        payload=payload,
        resumen=resumen,
        conversacion_id=conversacion_id,
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
