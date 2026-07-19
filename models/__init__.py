# models package — Pydantic v2 typed contracts for AI-callable services

from .common import (
    T,
    Money,
    PaginationParams,
    PaginatedResponse,
    SuccessResponse,
    ErrorDetail,
    ErrorResponse,
    UndoToken,
    ServiceResult,
    OperationLog,
)

from .trip_models import (
    TripStop,
    TripCreate,
    TripUpdate,
    TripResult,
    TripCreateResult,
    TripListResult,
)

from .route_models import (
    RouteStop,
    RouteCalculateRequest,
    RouteResult,
    RouteCalculationResult,
)

from .dispatch_models import (
    DispatchCreate,
    DispatchAssign,
    DispatchCancel,
    DispatchResult,
    UnassignedTrip,
    AvailableTruck,
    DispatchBoardResult,
    DispatchCreateResult,
    DispatchBoardResult_Typed,
)

from .vehicle_models import (
    VehicleCreate,
    VehicleUpdate,
    VehicleSearchRequest,
    VehicleHealthScore,
    VehicleResult,
    VehicleCreateResult,
    VehicleSearchResult,
)

from .client_models import (
    ClientContact,
    ClientCreate,
    ClientUpdate,
    ClientResult,
    ClientCreateResult,
    ClientListResult,
)

from .invoice_models import (
    InvoiceLineItem,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceFinalizeRequest,
    InvoiceResult,
    InvoiceCreateResult,
    InvoiceListResult,
)

from .receipt_models import (
    ReceiptLineItem,
    ReceiptCreate,
    ReceiptResult,
    ReceiptCreateResult,
)

from .payment_models import (
    PaymentProfileCreate,
    PaymentProfileResult,
    PaymentBatchRequest,
    PaymentBatchResult,
    PaymentBatchCreateResult,
)

from .proforma_models import (
    ProformaCreate,
    ProformaResult,
    ProformaCreateResult,
)

from .document_models import (
    DocumentUpload,
    DocumentResult,
    DocumentUploadResult,
    DocumentListResult,
)

from .ocr_models import (
    OcrProcessRequest,
    ExtractedFields,
    MatchedTrip,
    OcrResult,
    OcrProcessResult,
)

from .analytics_models import (
    AnalyticsRequest,
    RevenueReport,
    OverdueReport,
    KpiDashboard,
    AnalyticsReportResult,
)

from .export_models import (
    ExportRequest,
    ExportResult,
    ExportOperationResult,
)

from .cmr_models import (
    CmrGenerateRequest,
    CmrResult,
    CmrGenerateResult,
)

from .cost_models import (
    CostEstimateRequest,
    CostBreakdown,
    CostEstimateResult,
    CostEstimateOperationResult,
)

from .driver_models import (
    DriverCreate,
    DriverUpdate,
    DriverHoursCheck,
    DriverHoursResult,
    DriverResult,
    TruckAssignment,
    DriverCreateResult,
    DriverHoursCheckResult,
)

from .tacho_models import (
    TachoImportRequest,
    DriverActivity,
    VehicleActivity,
    TachoImportResult,
    DriverHoursAnalysis,
    FleetTachoSummary,
    TachoImportOperationResult,
    TachoAnalysisResult,
    TachoFleetSummaryResult,
)

from .calculator_models import (
    CalculationRequest,
    TripCalculationResult,
    CalculationOperationResult,
)

from .automail_models import (
    EmailTemplateCreate,
    SendReminderRequest,
    SendReminderResult,
    AutomailSendResult,
)

from .freight_exchange_models import (
    ProviderCredentials,
    ProviderSession,
    ProviderHealthCheck,
    ProviderCapabilities,
    GeoFilter,
    LoadSearchFilters,
    LoadSearchResult,
    SavedSearch,
    ImportResult,
    VehicleCompatibility,
    DriverCompatibility,
    LoadEvaluation,
    TruckMatchScore,
)

__all__ = [
    # common
    "T",
    "Money",
    "PaginationParams",
    "PaginatedResponse",
    "SuccessResponse",
    "ErrorDetail",
    "ErrorResponse",
    "UndoToken",
    "ServiceResult",
    "OperationLog",
    # trip
    "TripStop",
    "TripCreate",
    "TripUpdate",
    "TripResult",
    "TripCreateResult",
    "TripListResult",
    # route
    "RouteStop",
    "RouteCalculateRequest",
    "RouteResult",
    "RouteCalculationResult",
    # dispatch
    "DispatchCreate",
    "DispatchAssign",
    "DispatchCancel",
    "DispatchResult",
    "UnassignedTrip",
    "AvailableTruck",
    "DispatchBoardResult",
    "DispatchCreateResult",
    "DispatchBoardResult_Typed",
    # vehicle
    "VehicleCreate",
    "VehicleUpdate",
    "VehicleSearchRequest",
    "VehicleHealthScore",
    "VehicleResult",
    "VehicleCreateResult",
    "VehicleSearchResult",
    # client
    "ClientContact",
    "ClientCreate",
    "ClientUpdate",
    "ClientResult",
    "ClientCreateResult",
    "ClientListResult",
    # invoice
    "InvoiceLineItem",
    "InvoiceCreate",
    "InvoiceUpdate",
    "InvoiceFinalizeRequest",
    "InvoiceResult",
    "InvoiceCreateResult",
    "InvoiceListResult",
    # receipt
    "ReceiptLineItem",
    "ReceiptCreate",
    "ReceiptResult",
    "ReceiptCreateResult",
    # payment
    "PaymentProfileCreate",
    "PaymentProfileResult",
    "PaymentBatchRequest",
    "PaymentBatchResult",
    "PaymentBatchCreateResult",
    # proforma
    "ProformaCreate",
    "ProformaResult",
    "ProformaCreateResult",
    # document
    "DocumentUpload",
    "DocumentResult",
    "DocumentUploadResult",
    "DocumentListResult",
    # ocr
    "OcrProcessRequest",
    "ExtractedFields",
    "MatchedTrip",
    "OcrResult",
    "OcrProcessResult",
    # analytics
    "AnalyticsRequest",
    "RevenueReport",
    "OverdueReport",
    "KpiDashboard",
    "AnalyticsReportResult",
    # export
    "ExportRequest",
    "ExportResult",
    "ExportOperationResult",
    # cmr
    "CmrGenerateRequest",
    "CmrResult",
    "CmrGenerateResult",
    # cost
    "CostEstimateRequest",
    "CostBreakdown",
    "CostEstimateResult",
    "CostEstimateOperationResult",
    # driver
    "DriverCreate",
    "DriverUpdate",
    "DriverHoursCheck",
    "DriverHoursResult",
    "DriverResult",
    "TruckAssignment",
    "DriverCreateResult",
    "DriverHoursCheckResult",
    # calculator
    "CalculationRequest",
    "TripCalculationResult",
    "CalculationOperationResult",
    # automail
    "EmailTemplateCreate",
    "SendReminderRequest",
    "SendReminderResult",
    "AutomailSendResult",
    # freight exchange
    "ProviderCredentials",
    "ProviderSession",
    "ProviderHealthCheck",
    "ProviderCapabilities",
    "GeoFilter",
    "LoadSearchFilters",
    "LoadSearchResult",
    "SavedSearch",
    "ImportResult",
    "VehicleCompatibility",
    "DriverCompatibility",
    "LoadEvaluation",
    "TruckMatchScore",
    # tacho
    "TachoImportRequest",
    "DriverActivity",
    "VehicleActivity",
    "TachoImportResult",
    "DriverHoursAnalysis",
    "FleetTachoSummary",
    "TachoImportOperationResult",
    "TachoAnalysisResult",
    "TachoFleetSummaryResult",
]
