"""PySide6 view modules for the Operion ERP Qt branch."""

from ui.views.calculator_view import QtCalculatorView
from ui.views.overview_view import QtOverviewView
from ui.views.route_planner_view import QtRoutePlannerView
from ui.views.analytics_view import QtAnalyticsView
from ui.views.route_history_view import QtRouteHistoryView
from ui.views.history_view import QtHistoryView
from ui.views.settings_view import QtSettingsView
from ui.views.dispatch_board_view import QtDispatchBoardView
from ui.views.fleet_tracking_view import QtFleetTrackingView
from ui.views.fleet_tab import QtFleetTab
from ui.views.driver_manager import QtDriverManager
from ui.views.client_workspace import QtClientWorkspace
from ui.views.client_manager import QtClientManager
from ui.views.document_center_view import QtDocumentCenterView
from ui.views.maintenance_analytics_view import QtMaintenanceAnalyticsView
from ui.views.maintenance_control_panel import QtMaintenanceControlPanel
from ui.views.tacho_import_view import QtTachoImportView
from ui.views.generators_view import QtGeneratorsView
from ui.views.cmr_form_view import QtCmrFormView
from ui.views.invoice_editor import QtInvoiceEditor
from ui.views.dashboard import QtFleetDashboard

__all__ = [
    "QtCalculatorView", "QtOverviewView", "QtRoutePlannerView",
    "QtAnalyticsView", "QtRouteHistoryView", "QtHistoryView",
    "QtSettingsView", "QtDispatchBoardView", "QtFleetTrackingView",
    "QtFleetTab", "QtDriverManager", "QtClientWorkspace",
    "QtClientManager", "QtDocumentCenterView", "QtMaintenanceAnalyticsView",
    "QtMaintenanceControlPanel", "QtTachoImportView", "QtGeneratorsView",
    "QtCmrFormView", "QtInvoiceEditor", "QtFleetDashboard",
]
