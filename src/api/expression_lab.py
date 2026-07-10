import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_learner, get_db_session, get_model_router
from src.expression_lab.action_handler import ExpressionLabActionError
from src.expression_lab.schemas import (
    ActionRequest,
    ActionResponse,
    AttemptRequest,
    AttemptResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EventRequest,
    RegenerateBlockRequest,
    RegenerateSessionRequest,
    SessionDetail,
    SessionListResponse,
)
from src.expression_lab.service import (
    ExpressionLabError,
    ExpressionLabService,
    generate_expression_lab_session_task,
    session_summary,
)
from src.models.learner import Learner
from src.providers.router import ModelRouter


router = APIRouter(
    prefix="/api/learners/{learner_id}/expression-lab",
    tags=["expression-lab"],
)


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_expression_lab_session(
    learner_id: uuid.UUID,
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> CreateSessionResponse:
    service = ExpressionLabService(db, model_router)
    try:
        session = await service.create_session(learner_id=learner.id, request=request)
    except ExpressionLabError as exc:
        _raise_http_error(exc)
    # A background worker needs to observe the generating row and its AgentEpisode.
    await db.commit()
    background_tasks.add_task(generate_expression_lab_session_task, session.id)
    return CreateSessionResponse(session_id=session.id)


@router.get("/sessions", response_model=SessionListResponse)
async def list_expression_lab_sessions(
    learner_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=50),
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> SessionListResponse:
    service = ExpressionLabService(db)
    sessions, pending_count = await service.list_sessions(learner_id=learner.id, limit=limit)
    items = [session_summary(session) for session in sessions]
    return SessionListResponse(sessions=items, pending_count=pending_count)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_expression_lab_session(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> SessionDetail:
    service = ExpressionLabService(db)
    try:
        session = await service.get_session(learner_id=learner.id, session_id=session_id)
        return SessionDetail.model_validate(await service.session_detail(session))
    except ExpressionLabError as exc:
        _raise_http_error(exc)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expression_lab_session(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        await ExpressionLabService(db).delete_session(
            learner_id=learner.id, session_id=session_id
        )
    except ExpressionLabError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sessions/{session_id}/regenerate",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_expression_lab_generation(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: RegenerateSessionRequest | None = None,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> CreateSessionResponse:
    try:
        session = await ExpressionLabService(db).retry_generation(
            learner_id=learner.id, session_id=session_id
        )
    except ExpressionLabError as exc:
        _raise_http_error(exc)
    await db.commit()
    background_tasks.add_task(
        generate_expression_lab_session_task,
        session.id,
        "retry",
        request.instruction if request is not None else None,
    )
    return CreateSessionResponse(session_id=session.id)


@router.post(
    "/sessions/{session_id}/blocks/{block_id}/regenerate",
    response_model=SessionDetail,
)
async def regenerate_expression_lab_block(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    block_id: str,
    request: RegenerateBlockRequest | None = None,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> SessionDetail:
    try:
        service = ExpressionLabService(db, model_router)
        session = await service.regenerate_block(
            learner_id=learner.id,
            session_id=session_id,
            block_id=block_id,
            instruction=request.instruction if request is not None else None,
        )
        return SessionDetail.model_validate(await service.session_detail(session))
    except ExpressionLabError as exc:
        _raise_http_error(exc)


@router.post(
    "/sessions/{session_id}/attempts",
    response_model=AttemptResponse,
)
async def submit_expression_lab_attempt(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    request: AttemptRequest,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> AttemptResponse:
    try:
        return await ExpressionLabService(db).submit_attempt(
            learner_id=learner.id,
            session_id=session_id,
            request=request,
        )
    except ExpressionLabError as exc:
        _raise_http_error(exc)


@router.post(
    "/sessions/{session_id}/actions/{action_id}",
    response_model=ActionResponse,
)
async def execute_expression_lab_action(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    action_id: uuid.UUID,
    request: ActionRequest,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> ActionResponse:
    try:
        result = await ExpressionLabService(db, model_router).execute_action(
            learner_id=learner.id,
            session_id=session_id,
            action_id=action_id,
            request=request,
        )
    except (ExpressionLabError, ExpressionLabActionError) as exc:
        _raise_http_error(exc)
    public_status = {
        "pending": "candidate",
        "applying": "saving",
        "applied": "saved",
    }.get(result.status, result.status)
    target = (
        {"type": result.applied_target_type, "id": result.applied_target_id}
        if result.applied_target_type and result.applied_target_id
        else None
    )
    return ActionResponse(
        action_id=result.action_id,
        status=public_status,
        applied_target=target,
        applied_target_type=result.applied_target_type,
        applied_target_id=result.applied_target_id,
        payload=result.payload,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionDetail)
async def complete_expression_lab_session(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> SessionDetail:
    service = ExpressionLabService(db)
    try:
        session = await service.complete_session(
            learner_id=learner.id, session_id=session_id
        )
        return SessionDetail.model_validate(await service.session_detail(session))
    except ExpressionLabError as exc:
        _raise_http_error(exc)


@router.post("/sessions/{session_id}/events", status_code=status.HTTP_204_NO_CONTENT)
async def record_expression_lab_event(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    request: EventRequest,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        await ExpressionLabService(db).record_client_event(
            learner_id=learner.id,
            session_id=session_id,
            request=request,
        )
    except ExpressionLabError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _raise_http_error(exc: Exception) -> None:
    if isinstance(exc, ExpressionLabError):
        status_code = exc.status_code
        code = exc.code
    elif isinstance(exc, ExpressionLabActionError):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "action_not_found"
            else status.HTTP_409_CONFLICT
            if exc.code in {"confirmation_required", "action_in_progress"}
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        code = exc.code
    else:
        status_code = status.HTTP_400_BAD_REQUEST
        code = "expression_lab_error"
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc)},
    ) from exc
