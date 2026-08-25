#!/usr/bin/env python3
"""Comprehensive translation of all untranslated keys in es.json."""
from __future__ import annotations

import json, os

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

# Load data
es_data = load_json(os.path.join(BASE, "es.json"))
en_data = load_json(os.path.join(BASE, "en.json"))
es_flat = flatten(es_data)
en_flat = flatten(en_data)

# Comprehensive translation map for ALL untranslated keys
T = {
    # === about section ===
    "about.page_title": "Acerca de - Operion ERP",
    "about.page_header": "Acerca de Operion",
    "about.page_header_desc": "Estamos construyendo el futuro del software de logística empresarial.",
    "about.story_title": "Nuestra Historia",
    "about.story_p1": "Operion fue fundada en 2024 con una misión clara: hacer que el software de logística de nivel empresarial sea accesible para flotas de todos los tamaños.",
    "about.story_p2": "Nuestro equipo combina décadas de experiencia en logística, ingeniería de software e IA para construir herramientas que resuelvan problemas del mundo real.",
    "about.story_p3": "Hoy, Operion impulsa flotas en toda Europa, ayudándoles a planificar de forma más inteligente, despachar más rápido y crecer más.",
    "about.values_title": "Nuestros Valores",
    "about.values_desc": "Los principios que guían cada decisión que tomamos.",
    "about.value_customer_title": "El Cliente Primero",
    "about.value_customer_desc": "Cada función que construimos comienza con las necesidades reales y los comentarios de los clientes.",
    "about.value_reliability_title": "Fiabilidad",
    "about.value_reliability_desc": "Sus operaciones dependen de nuestro software. Nos tomamos esa responsabilidad muy en serio.",
    "about.value_innovation_title": "Innovación",
    "about.value_innovation_desc": "Invertimos fuertemente en I+D para llevar IA y optimización de vanguardia a la logística.",
    "about.value_transparency_title": "Transparencia",
    "about.value_transparency_desc": "Precios claros, comunicación honesta y sin comisiones ocultas.",
    "about.value_security_title": "Seguridad",
    "about.value_security_desc": "Cifrado de nivel empresarial, cumplimiento GDPR y auditorías de seguridad periódicas.",
    "about.value_partnership_title": "Asociación",
    "about.value_partnership_desc": "No solo vendemos software. Nos asociamos con nuestros clientes para su éxito.",
    "about.team_title": "Nuestro Equipo",
    "about.team_desc": "Nuestro equipo combina décadas de experiencia en logística, ingeniería de software e IA.",

    # === auth section ===
    "auth.login_title": "Iniciar Sesión — Operion ERP",
    "auth.login_back": "Volver al inicio",
    "auth.login_brand": "Operion",
    "auth.login_welcome": "Bienvenido de nuevo",
    "auth.login_subtitle": "Inicie sesión en su cuenta de Operion",
    "auth.email_label": "Correo electrónico",
    "auth.email_placeholder": "usted@empresa.com",
    "auth.password_label": "Contraseña",
    "auth.forgot_password": "¿Olvidó su contraseña?",
    "auth.password_placeholder": "Introduzca su contraseña",
    "auth.hide_password": "Ocultar contraseña",
    "auth.show_password": "Mostrar contraseña",
    "auth.signing_in": "Iniciando sesión...",
    "auth.sign_in": "Iniciar sesión",
    "auth.no_account": "¿No tiene una cuenta?",
    "auth.sign_up_link": "Registrarse",
    "auth.signed_in_success": "¡Sesión iniciada correctamente!",
    "auth.sign_in_failed": "Error al iniciar sesión",
    "auth.validation_invalid_email": "Introduzca un correo electrónico válido",
    "auth.validation_password_required": "La contraseña es obligatoria",
    "auth.validation_password_max": "La contraseña debe tener como máximo 72 caracteres",
    "auth.register_title": "Crear Cuenta — Operion ERP",
    "auth.register_back": "Volver al inicio",
    "auth.register_brand": "Operion",
    "auth.register_welcome": "Cree su cuenta",
    "auth.register_subtitle": "Comience su prueba gratuita de 14 días",
    "auth.name_label": "Nombre Completo",
    "auth.name_placeholder": "Juan Pérez",
    "auth.company_label": "Nombre de la Empresa (opcional)",
    "auth.company_placeholder": "Acme Inc.",
    "auth.password_min_hint": "Al menos 8 caracteres",
    "auth.confirm_password_label": "Confirmar Contraseña",
    "auth.confirm_password_placeholder": "Repita su contraseña",
    "auth.creating_account": "Creando cuenta...",
    "auth.create_account": "Crear cuenta",
    "auth.has_account": "¿Ya tiene una cuenta?",
    "auth.sign_in_link": "Iniciar sesión",
    "auth.account_created": "¡Cuenta creada correctamente!",
    "auth.create_account_failed": "Error al crear la cuenta",
    "auth.validation_name_min": "El nombre debe tener al menos 2 caracteres",
    "auth.validation_password_min": "La contraseña debe tener al menos 8 caracteres",
    "auth.validation_passwords_match": "Las contraseñas no coinciden",
}
T["auth.login_title"] = "Iniciar Sesión — Operion ERP"
T["auth.login_back"] = "Volver al inicio"
T["auth.login_brand"] = "Operion"
T["auth.login_welcome"] = "Bienvenido de nuevo"
T["auth.login_subtitle"] = "Inicie sesión en su cuenta de Operion"
T["auth.email_label"] = "Correo electrónico"
T["auth.email_placeholder"] = "usted@empresa.com"
T["auth.password_label"] = "Contraseña"
T["auth.forgot_password"] = "¿Olvidó su contraseña?"
T["auth.password_placeholder"] = "Introduzca su contraseña"
T["auth.hide_password"] = "Ocultar contraseña"
T["auth.show_password"] = "Mostrar contraseña"
T["auth.signing_in"] = "Iniciando sesión..."
T["auth.sign_in"] = "Iniciar sesión"
T["auth.no_account"] = "¿No tiene una cuenta?"
T["auth.sign_up_link"] = "Registrarse"
T["auth.signed_in_success"] = "¡Sesión iniciada correctamente!"
T["auth.sign_in_failed"] = "Error al iniciar sesión"
T["auth.validation_invalid_email"] = "Introduzca un correo electrónico válido"
T["auth.validation_password_required"] = "La contraseña es obligatoria"
T["auth.validation_password_max"] = "La contraseña debe tener como máximo 72 caracteres"
T["auth.register_title"] = "Crear Cuenta — Operion ERP"
T["auth.register_back"] = "Volver al inicio"
T["auth.register_brand"] = "Operion"
T["auth.register_welcome"] = "Cree su cuenta"
T["auth.register_subtitle"] = "Comience su prueba gratuita de 14 días"
T["auth.name_label"] = "Nombre Completo"
T["auth.name_placeholder"] = "Juan Pérez"
T["auth.company_label"] = "Nombre de la Empresa (opcional)"
T["auth.company_placeholder"] = "Acme Inc."
T["auth.password_min_hint"] = "Al menos 8 caracteres"
T["auth.confirm_password_label"] = "Confirmar Contraseña"
T["auth.confirm_password_placeholder"] = "Repita su contraseña"
T["auth.creating_account"] = "Creando cuenta..."
T["auth.create_account"] = "Crear cuenta"
T["auth.has_account"] = "¿Ya tiene una cuenta?"
T["auth.sign_in_link"] = "Iniciar sesión"
T["auth.account_created"] = "¡Cuenta creada correctamente!"
T["auth.create_account_failed"] = "Error al crear la cuenta"
T["auth.validation_name_min"] = "El nombre debe tener al menos 2 caracteres"
T["auth.validation_password_min"] = "La contraseña debe tener al menos 8 caracteres"
T["auth.validation_passwords_match"] = "Las contraseñas no coinciden"
