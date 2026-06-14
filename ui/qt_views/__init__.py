"""PySide6 view modules for the Operion ERP Qt branch."""

from ui.qt_views.qt_calculator_view import QtCalculatorView
from ui.qt_views.qt_overview_view import QtOverviewView
from ui.qt_views.qt_route_planner_view import QtRoutePlannerView
from ui.qt_views.qt_analytics_view import QtAnalyticsView
from ui.qt_views.qt_route_history_view import QtRouteHistoryView
from ui.qt_views.qt_history_view import QtHistoryView
from ui.qt_views.qt_settings_view import QtSettingsView
from ui.qt_views.qt_dispatch_board_view import QtDispatchBoardView
from ui.qt_views.qt_fleet_tracking_view import QtFleetTrackingView
from ui.qt_views.qt_fleet_tab import QtFleetTab
from ui.qt_views.qt_driver_manager import QtDriverManager
from ui.qt_views.qt_client_workspace import QtClientWorkspace
from ui.qt_views.qt_client_manager import QtClientManager
from ui.qt_views.qt_document_center_view import QtDocumentCenterView
from ui.qt_views.qt_maintenance_analytics_view import QtMaintenanceAnalyticsView
from ui.qt_views.qt_maintenance_control_panel import QtMaintenanceControlPanel
from ui.qt_views.qt_tacho_import_view import QtTachoImportView
from ui.qt_views.qt_generators_view import QtGeneratorsView
from ui.qt_views.qt_cmr_form_view import QtCmrFormView
from ui.qt_views.qt_invoice_editor import QtInvoiceEditor
from ui.qt_views.qt_dashboard import QtFleetDashboard

__all__ = [
    "QtCalculatorView", "QtOverviewView", "QtRoutePlannerView",
    "QtAnalyticsView", "QtRouteHistoryView", "QtHistoryView",
    "QtSettingsView", "QtDispatchBoardView", "QtFleetTrackingView",
    "QtFleetTab", "QtDriverManager", "QtClientWorkspace",
    "QtClientManager", "QtDocumentCenterView", "QtMaintenanceAnalyticsView",
    "QtMaintenanceControlPanel", "QtTachoImportView", "QtGeneratorsView",
    "QtCmrFormView", "QtInvoiceEditor", "QtFleetDashboard",
]
