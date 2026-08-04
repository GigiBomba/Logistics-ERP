"""PySide6 view modules for the Operion ERP Qt branch."""

from ui.views.analytics import QtAnalyticsView
from ui.views.automation_view import QtAutomationView
from ui.views.calculator_view import QtCalculatorView
from ui.views.copilot_view import CoPilotView as QtCopilotView
from ui.views.client_workspace import QtClientWorkspace
from ui.views.cmr_form_view import QtCmrFormView
from ui.views.dashboard import QtFleetDashboard
from ui.views.dispatch_board_view import QtDispatchBoardView
from ui.views.document_center_view import QtDocumentCenterView
from ui.views.driver_manager import QtDriverManager
from ui.views.fleet_tab import QtFleetTab
from ui.views.fleet_tracking_view import QtFleetTrackingView
from ui.views.freight_exchange.search_view import FreightSearchView
from ui.views.generators_view import QtGeneratorsView
from ui.views.history_view import QtHistoryView
from ui.views.invoice_editor import QtInvoiceEditor
from ui.views.maintenance_analytics_view import QtMaintenanceAnalyticsView
from ui.views.maintenance_control_panel import QtMaintenanceControlPanel
from ui.views.migration_center import QtMigrationCenterView
from ui.views.overview_view import QtOverviewView
from ui.views.route_history_view import QtRouteHistoryView
from ui.views.route_planner_view import QtRoutePlannerView
from ui.views.settings_view import QtSettingsView
from ui.views.tacho_import_view import QtTachoImportView
from ui.views.team_view import QtTeamView

__all__ = [
    "QtAnalyticsView",
    "QtAutomationView",
    "QtCalculatorView",
    "QtCopilotView",
    "QtClientWorkspace",
    "QtCmrFormView",
    "QtDispatchBoardView",
    "QtDocumentCenterView",
    "QtDriverManager",
    "QtFleetDashboard",
    "QtFleetTab",
    "QtFleetTrackingView",
    "FreightSearchView",
    "QtGeneratorsView",
    "QtHistoryView",
    "QtInvoiceEditor",
    "QtMaintenanceAnalyticsView",
    "QtMaintenanceControlPanel",
    "QtMigrationCenterView",
    "QtOverviewView",
    "QtRouteHistoryView",
    "QtRoutePlannerView",
    "QtSettingsView",
    "QtTachoImportView",
    "QtTeamView",
]
