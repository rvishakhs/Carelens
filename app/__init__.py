"""Barrel re-export module. Every other file in this package imports its
cross-module dependencies from here (`from app import X`) instead of reaching
into another module's file directly -- this is the single place that wires the
whole dependency graph together, in the order each piece actually needs its own
dependencies already defined.

Generated from the actual `from app import ...` usage across the codebase -- see
git history on this file for how it was derived. A few names are deliberately
NOT re-exported here because they are ambiguous per-module names, not unique
symbols: every module's `router.py` defines its own `router`, every module's
`module.py` defines its own `register()`, and `summaries`/`ai_insights` each
have their own distinct `SummaryFeedbackCreate`. Those are imported directly
from their owning submodule at each call site instead.
"""

from app.config import Settings, get_settings
from app.modules.ai_gateway.ports import LLMProvider, RESIDENT_PLACEHOLDER
from app.modules.ai_gateway.adapters.fake_llm import FakeLLMProvider
from app.modules.ai_gateway.adapters.local_llm import LocalLLMProvider
from app.modules.ai_gateway.adapters.real_llm import RealLLMProvider
from app.shared.telemetry import configure_logging, get_logger
from app.shared.database import (
    Base,
    TenantMixin,
    bootstrap_session,
    check_database,
    dispose_engine,
    init_engine,
    rls_session,
    system_session,
)
from app.modules.observations.models import Observation, ObservationType
from app.modules.observations.schemas import ObservationCreate, ObservationRead, ObservationSummary, is_plausible
from app.modules.handover.ports import AttentionRanker
from app.modules.handover.adapters.recency_ranker import RecencyAttentionRanker
from app.modules.identity.ports import IdentityProviderAdmin, TokenClaims, TokenVerifier
from app.modules.identity.adapters.keycloak_admin import KeycloakAdminClient
from app.modules.identity.models import CareHome, PermissionDefinition, Role, RolePermission, User
from app.shared.exceptions import (
    CareLensError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
    ValidationError,
)
from app.modules.identity.adapters.oidc_verifier import KeycloakTokenVerifier
from app.modules.floors.ports import FloorReader
from app.modules.floors.models import Floor, FloorType, UserFloorLink
from app.modules.floors.repository import FloorRepository
from app.modules.floors.dependencies import get_floor_reader_for
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import (
    CurrentUser,
    StaffCreate,
    StaffCreated,
    StaffCredentials,
    StaffUpdate,
    UserRead,
)
from app.modules.identity.dependencies import get_current_user, get_floor_scope
from app.modules.identity.permissions import ROLE_PERMISSIONS, Permission, require, role_has_permission
from app.modules.identity.permission_registry import PermissionRegistry
from app.modules.observations.ports import NoteStructurer, ObservationReader
from app.modules.observations.adapters.rule_based_structurer import RuleBasedNoteStructurer
from app.shared.events import DomainEvent, EventBus, InMemoryEventBus
from app.container import Container, build_container
from app.modules.ai_gateway.models import PseudonymMapping
from app.shared.security import generate_opaque_token, hmac_pseudonym
from app.modules.ai_gateway.repository import PseudonymMappingRepository
from app.modules.ai_gateway.pseudonymiser import Pseudonymiser
from app.modules.ai_gateway.service import AIGatewayService
from app.modules.ai_gateway.dependencies import get_ai_gateway_service
from app.modules.ai_gateway.schemas import GatewayTestRequest, GatewayTestResponse
from app.modules.ai_insights.events import AIAlertAcknowledged, AIAlertRaised
from app.modules.ai_insights.models import ResidentAIAlert, ResidentAIReport, ResidentAISummary, ResidentPrediction
from app.modules.ai_insights.schemas import (
    AlertAcknowledgeRequest,
    ResidentAIAlertRead,
    ResidentAIReportRead,
    ResidentAISummaryRead,
    ResidentPredictionRead,
)
from app.modules.ai_insights.ports import AIInsightReader
from app.modules.ai_insights.repository import AIInsightRepository
from app.modules.ai_insights.service import AIInsightService
from app.modules.audit.models import AuditAction, AuditEvent
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditEventRead
from app.modules.audit.service import AuditService
from app.modules.care_recording.events import CareEventRecorded
from app.modules.care_recording.models import (
    CareCategory,
    CareEvent,
    CareEventMeasurement,
    CareEventOption,
    CareTemplate,
    CareTemplateMeasurement,
    CareTemplateOption,
    CareTemplateSection,
)
from app.modules.care_recording.schemas import (
    CareCategoryRead,
    CareEventCreate,
    CareEventHistoryItem,
    CareEventRead,
    CareTemplateRead,
)
from app.modules.care_recording.ports import CareEventReader
from app.modules.care_recording.repository import CareRecordingRepository
from app.modules.care_recording.service import CareRecordingService
from app.modules.floors.events import FloorCreated, UserFloorAccessGranted, UserFloorAccessRevoked
from app.modules.floors.schemas import FloorCreate, FloorRead, UserFloorLinkCreate
from app.modules.floors.service import FloorService
from app.modules.handover.events import RecordViewed
from app.modules.residents.models import Resident, ResidentStatus
from app.modules.residents.schemas import (
    ActivityEntry,
    AdvanceDirectiveRead,
    AllergyRead,
    CarePlanGoalRead,
    CarePlanRead,
    CareRecordEntry,
    ContactRead,
    DiagnosisRead,
    LifeHistoryRead,
    PreferenceRead,
    ResidentCreate,
    ResidentListItem,
    ResidentOverview,
    ResidentRead,
    ResidentSummary,
    VitalsSnapshot,
    WeightPoint,
)
from app.modules.summaries.models import AIOutput, SummaryFeedbackRating
from app.modules.summaries.schemas import SummaryRead
from app.modules.handover.schemas import HandoverResidentCard
from app.modules.residents.ports import ResidentReader
from app.modules.summaries.ports import SummaryReader
from app.modules.handover.service import HandoverService
from app.modules.identity.events import (
    MfaChallengeFailed,
    StaffMemberCreated,
    StaffMemberUpdated,
    StaffPasswordReset,
    UserLoggedIn,
)
from app.modules.identity.service import IdentityService
from app.modules.medications.models import Medication, MedicationEvent, MedicationEventStatus, MedicationRoute
from app.modules.medications.events import MedicationEventRecorded
from app.modules.medications.schemas import (
    MedicationCreate,
    MedicationEventCreate,
    MedicationEventRead,
    MedicationRead,
    MedicationSchedule,
    MedicationScheduleEntry,
)
from app.modules.medications.ports import MedicationReader
from app.modules.medications.repository import MedicationRepository
from app.modules.medications.service import MedicationService
from app.modules.observations.repository import ObservationRepository
from app.modules.observations.dependencies import get_observation_reader
from app.modules.observations.events import ObservationRecorded
from app.modules.observations.service import ObservationService
from app.modules.residents.repository import ResidentRepository
from app.modules.residents.dependencies import get_resident_reader, get_scoped_resident_reader
from app.modules.residents.detail_repository import ResidentDetailRepository
from app.modules.residents.events import ResidentCreated
from app.modules.residents.service import ResidentService
from app.modules.residents.router import care_plans_router
from app.modules.summaries.repository import SummaryRepository
from app.modules.summaries.events import SummaryGenerated, SummaryReviewed
from app.modules.summaries.service import SummaryService
from app.modules.summaries.dependencies import get_summary_reader, get_summary_service
from app.shared.celery import celery_app
from app.shared.redis import check_redis, close_redis, init_redis
from app.workers.tasks.events import care_event_recorded
