from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from match_service.domain.like import Like, LikeStatus
from match_service.domain.match import Match
from match_service.protocols.like.repository import LikeRepositoryProtocol
from match_service.protocols.match.repository import MatchRepositoryProtocol
from match_service.protocols.outbox.repository import OutboxRepositoryProtocol
from match_service.usecases.handle_like.usecase import (
    LIKE_RECEIVED_EVENT,
    MATCH_CREATED_EVENT,
    HandleLike,
    HandleLikeDuplicateError,
)


def _make_like(
    *,
    id: int = 1,
    liker_telegram_id: int = 100,
    liked_telegram_id: int = 200,
    status: LikeStatus = LikeStatus.LIKED,
) -> Like:
    return Like(
        id=id,
        liker_telegram_id=liker_telegram_id,
        liked_telegram_id=liked_telegram_id,
        status=status,
        created_at=datetime.now(tz=UTC),
    )


def _make_match(
    *,
    id: int = 1,
    user1_telegram_id: int = 100,
    user2_telegram_id: int = 200,
) -> Match:
    return Match(
        id=id,
        user1_telegram_id=user1_telegram_id,
        user2_telegram_id=user2_telegram_id,
        created_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_like_repository(mock_session: AsyncMock) -> AsyncMock:
    repo = AsyncMock(spec=LikeRepositoryProtocol)

    @asynccontextmanager
    async def _context():
        yield mock_session

    repo.context = _context
    repo.insert_like = AsyncMock(return_value=_make_like())
    repo.exists_reverse_like = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_match_repository(mock_session: AsyncMock) -> AsyncMock:
    repo = AsyncMock(spec=MatchRepositoryProtocol)

    @asynccontextmanager
    async def _context():
        yield mock_session

    repo.context = _context
    repo.insert_match = AsyncMock(return_value=(_make_match(), None))
    return repo


@pytest.fixture
def mock_outbox_repository(mock_session: AsyncMock) -> AsyncMock:
    repo = AsyncMock(spec=OutboxRepositoryProtocol)

    @asynccontextmanager
    async def _context():
        yield mock_session

    repo.context = _context
    repo.insert_event = AsyncMock()
    return repo


@pytest.fixture
def mock_valkey() -> AsyncMock:
    client = AsyncMock()
    client.set = AsyncMock()
    return client


@pytest.fixture
def usecase(
    mock_like_repository: AsyncMock,
    mock_match_repository: AsyncMock,
    mock_outbox_repository: AsyncMock,
    mock_valkey: AsyncMock,
) -> HandleLike[AsyncMock]:
    return HandleLike[AsyncMock](
        like_repository=mock_like_repository,
        match_repository=mock_match_repository,
        outbox_repository=mock_outbox_repository,
        valkey=mock_valkey,
        match_debounce_ttl=300,
    )


class Test_HandleLike:
    async def test_non_mutual_like_inserts_like_and_returns_no_match(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
        mock_match_repository: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        request = HandleLike.Request(
            liker_telegram_id=100,
            liked_telegram_id=200,
        )

        response = await usecase.execute(request)

        mock_like_repository.insert_like.assert_called_once()
        mock_like_repository.exists_reverse_like.assert_called_once_with(mock_session, 100, 200)
        mock_match_repository.insert_match.assert_not_called()
        assert response.is_new_match is False
        assert response.match is None
        assert response.like.liker_telegram_id == 100
        assert response.like.liked_telegram_id == 200

    async def test_mutual_like_creates_match_and_outbox_event(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
        mock_match_repository: AsyncMock,
        mock_outbox_repository: AsyncMock,
        mock_valkey: AsyncMock,
    ) -> None:
        mock_like_repository.exists_reverse_like = AsyncMock(return_value=True)
        match = _make_match(id=42, user1_telegram_id=100, user2_telegram_id=200)
        mock_match_repository.insert_match = AsyncMock(return_value=(match, None))

        request = HandleLike.Request(
            liker_telegram_id=100,
            liked_telegram_id=200,
        )

        response = await usecase.execute(request)

        assert response.is_new_match is True
        assert response.match == match
        mock_match_repository.insert_match.assert_called_once()
        call_args = mock_match_repository.insert_match.call_args
        saved_request = call_args.args[1]
        assert saved_request.user1_telegram_id == 100
        assert saved_request.user2_telegram_id == 200

        assert mock_outbox_repository.insert_event.call_count == 2
        first_outbox_request = mock_outbox_repository.insert_event.call_args_list[0].args[1]
        second_outbox_request = mock_outbox_repository.insert_event.call_args_list[1].args[1]
        assert first_outbox_request.event_type == LIKE_RECEIVED_EVENT
        assert first_outbox_request.payload == {
            "liker_telegram_id": 100,
            "liked_telegram_id": 200,
        }
        assert second_outbox_request.event_type == MATCH_CREATED_EVENT
        assert second_outbox_request.payload["match_id"] == 42

        mock_valkey.set.assert_called_once()
        assert mock_valkey.set.call_args.args[0] == "match_activity:42"
        assert isinstance(mock_valkey.set.call_args.args[1], str)
        assert mock_valkey.set.call_args.kwargs == {"nx": True, "ex": 300}

    async def test_mutual_like_flow_requires_second_like_to_create_match(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
        mock_match_repository: AsyncMock,
        mock_outbox_repository: AsyncMock,
        mock_valkey: AsyncMock,
    ) -> None:
        first_like = _make_like(id=1, liker_telegram_id=100, liked_telegram_id=200)
        second_like = _make_like(id=2, liker_telegram_id=200, liked_telegram_id=100)
        match = _make_match(id=77, user1_telegram_id=200, user2_telegram_id=100)

        mock_like_repository.insert_like = AsyncMock(side_effect=[first_like, second_like])
        mock_like_repository.exists_reverse_like = AsyncMock(side_effect=[False, True])
        mock_match_repository.insert_match = AsyncMock(return_value=(match, None))

        first_response = await usecase.execute(
            HandleLike.Request(liker_telegram_id=100, liked_telegram_id=200),
        )
        second_response = await usecase.execute(
            HandleLike.Request(liker_telegram_id=200, liked_telegram_id=100),
        )

        assert first_response.is_new_match is False
        assert first_response.match is None
        assert second_response.is_new_match is True
        assert second_response.match == match

        assert mock_like_repository.insert_like.call_count == 2
        first_like_request = mock_like_repository.insert_like.call_args_list[0].args[1]
        second_like_request = mock_like_repository.insert_like.call_args_list[1].args[1]
        assert first_like_request.liker_telegram_id == 100
        assert first_like_request.liked_telegram_id == 200
        assert second_like_request.liker_telegram_id == 200
        assert second_like_request.liked_telegram_id == 100

        mock_match_repository.insert_match.assert_called_once()
        match_request = mock_match_repository.insert_match.call_args.args[1]
        assert match_request.user1_telegram_id == 200
        assert match_request.user2_telegram_id == 100

        assert mock_outbox_repository.insert_event.call_count == 3
        outbox_event_types = [
            call.args[1].event_type for call in mock_outbox_repository.insert_event.call_args_list
        ]
        assert outbox_event_types == [
            LIKE_RECEIVED_EVENT,
            LIKE_RECEIVED_EVENT,
            MATCH_CREATED_EVENT,
        ]

        mock_valkey.set.assert_called_once()
        assert mock_valkey.set.call_args.args[0] == "match_activity:77"

    async def test_duplicate_like_raises_handle_like_duplicate_error(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        mock_like_repository.insert_like = AsyncMock(side_effect=IntegrityError("", "", Exception()))

        request = HandleLike.Request(
            liker_telegram_id=100,
            liked_telegram_id=200,
        )

        with pytest.raises(HandleLikeDuplicateError) as exc_info:
            await usecase.execute(request)
        assert "100" in str(exc_info.value)
        assert "200" in str(exc_info.value)

    async def test_like_status_passed_through(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
    ) -> None:
        mock_like_repository.insert_like = AsyncMock(return_value=_make_like(status=LikeStatus.PASSED))

        request = HandleLike.Request(
            liker_telegram_id=100,
            liked_telegram_id=200,
            status=LikeStatus.PASSED,
        )

        response = await usecase.execute(request)

        call_args = mock_like_repository.insert_like.call_args
        saved_request = call_args.args[1]
        assert saved_request.status == LikeStatus.PASSED
        assert response.like.status == LikeStatus.PASSED

    async def test_valkey_not_set_when_no_match(
        self,
        usecase: HandleLike[AsyncMock],
        mock_valkey: AsyncMock,
    ) -> None:
        request = HandleLike.Request(
            liker_telegram_id=100,
            liked_telegram_id=200,
        )

        await usecase.execute(request)

        mock_valkey.set.assert_not_called()

    async def test_returns_like_with_correct_fields(
        self,
        usecase: HandleLike[AsyncMock],
        mock_like_repository: AsyncMock,
    ) -> None:
        like = _make_like(id=99, liker_telegram_id=777, liked_telegram_id=888)
        mock_like_repository.insert_like = AsyncMock(return_value=like)

        request = HandleLike.Request(
            liker_telegram_id=777,
            liked_telegram_id=888,
        )

        response = await usecase.execute(request)

        assert response.like.id == 99
        assert response.like.liker_telegram_id == 777
        assert response.like.liked_telegram_id == 888
