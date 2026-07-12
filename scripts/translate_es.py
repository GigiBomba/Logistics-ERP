#!/usr/bin/env python3
"""Translate ALL untranslated English values in es.json to Spanish."""
import json, os, re

BASE = os.path.join(os.path.dirname(__file__), os.pardir, "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def flatten(d, prefix=""):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = v
    return items

def set_nested(d, key_parts, value):
    cur = d
    for p in key_parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[key_parts[-1]] = value

es_data = load_json(os.path.join(BASE, "es.json"))
en_data = load_json(os.path.join(BASE, "en.json"))
es_flat = flatten(es_data)
en_flat = flatten(en_data)

# Find untranslated keys
untranslated = {k for k in en_flat if k in es_flat and isinstance(es_flat[k], str) and es_flat[k] == en_flat[k]}
print(f"Untranslated keys: {len(untranslated)}")
print(f"Total keys: {len(en_flat)}")

# Load manual translations
map_path = os.path.join(os.path.dirname(__file__), "translation_map.json")
if os.path.exists(map_path):
    with open(map_path, "r", encoding="utf-8") as f:
        manual = json.load(f)
else:
    manual = {}

# Apply any manual translations
for key, val in manual.items():
    if key in untranslated:
        parts = key.split(".")
        set_nested(es_data, parts, val)
        untranslated.discard(key)

# For remaining untranslated keys, apply pattern-based translation
remaining = sorted(untranslated)

# Common English->Spanish word/phrase replacements
WORD_MAP = {
    "Active": "Activo", "Inactive": "Inactivo", "All": "Todos",
    "Error": "Error", "Success": "Correcto", "Warning": "Advertencia",
    "Info": "Información", "Critical": "Crítico",
    "Save": "Guardar", "Cancel": "Cancelar", "Delete": "Eliminar",
    "Edit": "Editar", "Add": "Añadir", "Remove": "Eliminar",
    "Create": "Crear", "Generate": "Generar", "Export": "Exportar",
    "Import": "Importar", "Upload": "Subir", "Download": "Descargar",
    "Search": "Buscar", "Find": "Buscar", "Reset": "Restablecer",
    "Refresh": "Actualizar", "Update": "Actualizar",
    "View": "Ver", "Show": "Mostrar", "Hide": "Ocultar",
    "Open": "Abrir", "Close": "Cerrar", "Next": "Siguiente",
    "Previous": "Anterior", "Prev": "Anterior", "Back": "Atrás",
    "First": "Primero", "Last": "Último", "New": "Nuevo",
    "Select": "Seleccionar", "Clear": "Limpiar", "Apply": "Aplicar",
    "Yes": "Sí", "No": "No", "OK": "OK", "None": "Ninguno",
    "Name": "Nombre", "Title": "Título", "Description": "Descripción",
    "Date": "Fecha", "Time": "Hora", "Status": "Estado",
    "Type": "Tipo", "Category": "Categoría", "Amount": "Importe",
    "Total": "Total", "Price": "Precio", "Cost": "Coste",
    "Profit": "Beneficio", "Revenue": "Ingresos", "Margin": "Margen",
    "Rate": "Tarifa", "Distance": "Distancia", "Duration": "Duración",
    "Driver": "Conductor", "Truck": "Camión", "Vehicle": "Vehículo",
    "Client": "Cliente", "Customer": "Cliente", "User": "Usuario",
    "Email": "Correo electrónico", "Phone": "Teléfono",
    "Address": "Dirección", "Password": "Contraseña",
    "Settings": "Ajustes", "Configuration": "Configuración",
    "Dashboard": "Panel", "Panel": "Panel",
    "Report": "Informe", "Reports": "Informes",
    "Invoice": "Factura", "Invoices": "Facturas",
    "Document": "Documento", "Documents": "Documentos",
    "Trip": "Viaje", "Trips": "Viajes",
    "Route": "Ruta", "Routes": "Rutas",
    "Fleet": "Flota", "Maintenance": "Mantenimiento",
    "Fuel": "Combustible", "Toll": "Peaje", "Tolls": "Peajes",
    "Salary": "Salario", "Expense": "Gasto", "Expenses": "Gastos",
    "Alert": "Alerta", "Alerts": "Alertas",
    "Notification": "Notificación", "Message": "Mensaje",
    "File": "Archivo", "Files": "Archivos",
    "Image": "Imagen", "Images": "Imágenes",
    "Help": "Ayuda", "About": "Acerca de",
    "Language": "Idioma", "Currency": "Moneda",
    "Unit": "Unidad", "Units": "Unidades",
    "Year": "Año", "Month": "Mes", "Day": "Día",
    "Week": "Semana", "Hour": "Hora", "Minute": "Minuto",
    "Second": "Segundo", "Today": "Hoy",
    "From": "Desde", "To": "Hasta", "By": "Por",
    "Label": "Etiqueta", "Value": "Valor",
    "Default": "Por defecto", "Custom": "Personalizado",
    "Manual": "Manual", "Automatic": "Automático",
    "Enabled": "Activado", "Disabled": "Desactivado",
    "Item": "Elemento", "Items": "Elementos",
    "List": "Lista", "Table": "Tabla",
    "Form": "Formulario", "Field": "Campo",
    "Button": "Botón", "Link": "Enlace",
    "Header": "Encabezado", "Footer": "Pie de página",
    "Top": "Superior", "Bottom": "Inferior",
    "Left": "Izquierda", "Right": "Derecha",
    "Summary": "Resumen", "Detail": "Detalle",
    "Details": "Detalles", "Options": "Opciones",
    "Actions": "Acciones", "Action": "Acción",
    "Confirm": "Confirmar", "Cancel": "Cancelar",
    "Done": "Hecho", "Complete": "Completar",
    "Start": "Inicio", "Stop": "Detener",
    "Begin": "Comenzar", "End": "Fin",
    "Source": "Origen", "Destination": "Destino",
    "Origin": "Origen", "Target": "Destino",
    "Loading": "Cargando", "Processing": "Procesando",
    "Calculating": "Calculando", "Saving": "Guardando",
    "Print": "Imprimir", "Preview": "Vista previa",
    "Share": "Compartir", "Send": "Enviar",
    "Receive": "Recibir", "Accept": "Aceptar",
    "Reject": "Rechazar", "Approve": "Aprobar",
    "Decline": "Rechazar", "Submit": "Enviar",
    "Register": "Registrarse", "Login": "Iniciar sesión",
    "Logout": "Cerrar sesión", "Sign in": "Iniciar sesión",
    "Sign out": "Cerrar sesión", "Sign up": "Registrarse",
    "Account": "Cuenta", "Profile": "Perfil",
    "License": "Permiso", "Permiso": "Permiso",
    "Contract": "Contrato", "Agreement": "Acuerdo",
    "Version": "Versión", "History": "Historial",
    "Archive": "Archivar", "Archived": "Archivado",
    "Template": "Plantilla", "Sample": "Ejemplo",
    "Note": "Nota", "Notes": "Notas",
    "Comment": "Comentario", "Comments": "Comentarios",
    "Info": "Información", "Information": "Información",
    "Warning": "Advertencia", "Danger": "Peligro",
    "Required": "Obligatorio", "Optional": "Opcional",
    "Invalid": "Inválido", "Valid": "Válido",
    "Empty": "Vacío", "Blank": "En blanco",
    "Available": "Disponible", "Unavailable": "No disponible",
    "Free": "Libre", "Busy": "Ocupado",
    "Queue": "Cola", "Queue Size": "Tamaño de cola",
    "Coverage": "Cobertura", "Stopped": "Detenido",
    "Label": "Etiqueta", "Filter": "Filtro",
    "Contact": "Contacto", "Contacts": "Contactos",
    "Group": "Grupo", "Billed": "Facturado",
    "Outstanding": "Pendiente", "Overdue": "Vencido",
    "Unpaid": "Impago", "Paid": "Pagado",
    "Invoiced": "Facturado", "Identifier": "Identificador",
    "Priority": "Prioridad", "Normal": "Normal",
    "High": "Alta", "Low": "Baja",
    "Medium": "Media", "Max": "Máx",
    "Min": "Mín", "Avg": "Media",
    "Beginner": "Principiante", "Expert": "Experto",
    "Photo": "Foto", "Photos": "Fotos",
    "Resolved": "Resuelto", "Unresolved": "No resuelto",
    "Due": "Vencido", "Overdue": "Vencido",
    "Expired": "Vencido", "Expiry": "Vencimiento",
    "Expiring": "Por vencer", "Expires": "Vence",
    "Remaining": "Restante", "Remaining": "Restantes",
    "Mileage": "Kilometraje", "Odometer": "Odómetro",
    "Schedule": "Programación", "Scheduled": "Programado",
    "Timeline": "Cronología", "Calendar": "Calendario",
    "Check": "Verificar", "Test": "Probar",
    "Backup": "Copia de seguridad", "Restore": "Restaurar",
    "Uploaded": "Subido", "Downloaded": "Descargado",
    "Connected": "Conectado", "Disconnected": "Desconectado",
    "Active": "Activo", "Inactive": "Inactivo",
    "Enabled": "Habilitado", "Disabled": "Deshabilitado",
    "Tracking": "Seguimiento", "Tracker": "Rastreador",
    "Notification": "Notificación", "Reminder": "Recordatorio",
    "Copy": "Copiar", "Paste": "Pegar",
    "Cut": "Cortar", "Select All": "Seleccionar todo",
    "Designed for real logistics results": "Diseñado para resultados logísticos reales",
    "Control Panel Title": "Panel de Control",
    "Driver Activity Title": "Actividad del Conductor",
    "Section Status Title": "Título de Estado de Sección",
    "Tacho Subtitle": "Subtítulo de Tacógrafo",
    "Import Card Title": "Importar Tarjeta",
    "Unassigned": "Sin Asignar",
    "Recipient": "Destinatario",
    "Body": "Cuerpo",
    "Subject": "Asunto",
    "Sent": "Enviado",
    "Logs": "Registros",
    "No Data": "Sin Datos",
    "Attachment": "Adjunto",
    "Attachments": "Adjuntos",
    "Browse": "Examinar",
    "Choose File": "Elegir Archivo",
    "No file selected": "Ningún archivo seleccionado",
    "Drop files here or click to select": "Suelte los archivos aquí o haga clic para seleccionar",
    "DDD / TGD / other tachograph files": "DDD / TGD / otros archivos de tacógrafo",
    "Select tachograph file": "Seleccionar archivo de tacógrafo",
    "No imports yet": "Sin importaciones aún",
    "Import a tachograph file to see the history": "Importe un archivo de tacógrafo para ver el historial",
    "Drop images or PDFs here": "Suelte imágenes o PDFs aquí",
    "Send Customer Package": "Enviar Paquete al Cliente",
    "Prepare Customer Package": "Preparar Paquete para el Cliente",
    "Package for {trip}": "Paquete para {trip}",
    "Customer Package": "Paquete del Cliente",
    "No documents to package": "No hay documentos para empaquetar",
    "Selected": "Seleccionado",
    "Loaded": "Cargado",
    "Load": "Cargar",
    "Draft": "Borrador",
    "Draft Saved": "Borrador Guardado",
    "No drafts found": "No se encontraron borradores",
    "Draft Saved Msg": "Mensaje de Borrador Guardado",
    "Draft Loaded": "Borrador Cargado",
}

# Apply WORD_MAP to remaining keys using pattern matching
for key in list(remaining):
    en_val = en_flat[key]
    
    # Skip non-string values or already-translated patterns
    if not isinstance(en_val, str) or not en_val:
        remaining.remove(key)
        continue
    
    # Direct word map lookup
    if en_val in WORD_MAP:
        es_val = WORD_MAP[en_val]
        parts = key.split(".")
        set_nested(es_data, parts, es_val)
        remaining.remove(key)
        continue

# Print remaining untranslated keys
if remaining:
    print(f"\nStill untranslated: {len(remaining)} keys")
    for k in remaining[:20]:
        print(f"  {k} = {en_flat[k]!r}")
    if len(remaining) > 20:
        print(f"  ... and {len(remaining)-20} more")
else:
    print("All keys translated!")

# Write result
with open(os.path.join(BASE, "es.json"), "w", encoding="utf-8") as f:
    json.dump(es_data, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("\nes.json written successfully!")
