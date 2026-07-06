from __future__ import annotations

import html
import json
import urllib.parse
from typing import Any, Dict, Iterable, Optional

UI_LANG_COOKIE = "repliq_ui_lang"
UI_SUPPORTED_LANGUAGES = ("lv", "ru", "en")
UI_DEFAULT_LANGUAGE = "en"
UI_FOUNDATION_VERSION = "cx1.1"

_UI_TEXT: Dict[str, Dict[str, str]] = {
    "en": {
        "app.name": "Repliq",
        "app.tagline": "AI receptionist workspace",
        "nav.dashboard": "Dashboard",
        "nav.get_started": "Get started",
        "nav.workspace": "Workspace",
        "nav.health": "Setup health",
        "nav.account": "Account",
        "nav.logout": "Log out",
        "nav.open_menu": "Open menu",
        "nav.aria": "Owner navigation",
        "language.label": "Interface language",
        "language.lv": "LV",
        "language.ru": "RU",
        "language.en": "EN",
        "common.loading": "Loading…",
        "common.load": "Refresh",
        "common.open": "Open",
        "common.ready": "Ready",
        "common.attention": "Needs attention",
        "common.complete": "Complete",
        "common.support_controlled": "Managed with Repliq support",
        "common.no_items": "Nothing to show yet.",
        "common.technical_details": "Technical details",
        "common.secure_area": "Secure owner area",
        "common.error": "Something went wrong.",
        "login.title": "Welcome back",
        "login.subtitle": "Sign in to manage your Repliq workspace.",
        "login.tenant": "Workspace ID",
        "login.email": "Owner email",
        "login.code": "Login code",
        "login.button": "Sign in",
        "login.magic": "Use a magic link",
        "login.note": "Your login creates a secure owner session. Repliq never displays secret hashes or admin credentials on this page.",
        "login.required": "Enter the owner email and login code.",
        "login.checking": "Checking your details…",
        "login.success": "Signed in. Opening your dashboard…",
        "login.failed": "Sign-in failed.",
        "dashboard.title": "Dashboard",
        "dashboard.subtitle": "Your business setup, launch status and useful workspace shortcuts in one place.",
        "dashboard.business": "Business",
        "dashboard.owner": "Owner access",
        "dashboard.scope": "Workspace",
        "dashboard.scope_value": "Repliq for SMB",
        "dashboard.scope_note": "Owner-safe management area",
        "dashboard.setup": "Setup progress",
        "dashboard.setup_note": "Complete the remaining steps before going live.",
        "dashboard.auth": "Access status",
        "dashboard.links": "Workspace tools",
        "dashboard.tenant": "Workspace ID",
        "dashboard.session": "Session details",
        "dashboard.super_admin": "Support access",
        "get_started.badge": "Workspace active",
        "get_started.title": "Let’s finish your Repliq setup",
        "get_started.subtitle": "Review the recommended steps, complete your business information and run the final launch check.",
        "get_started.open_workspace": "Open workspace",
        "get_started.setup_health": "Setup health",
        "get_started.dashboard": "Dashboard",
        "get_started.handoff": "Setup overview",
        "get_started.next_steps": "Recommended next steps",
        "get_started.finish": "Finish and review",
        "get_started.launch_review": "Final launch review",
        "get_started.launch_smoke": "Launch check",
        "get_started.preview": "Client preview",
        "get_started.account": "Account",
        "get_started.status": "Owner-safe status",
        "get_started.handoff_ready": "Setup handoff ready",
        "get_started.workspace_complete": "Workspace setup complete",
        "get_started.health_complete": "Setup health complete",
        "get_started.progress": "Workspace {done}/{total} · {percent}% · Setup health {health}%",
        "get_started.no_steps": "No setup steps were returned.",
        "get_started.login_required": "Owner sign-in is required.",
        "workspace.title": "Workspace setup",
        "workspace.subtitle": "Manage the main setup areas of your Repliq workspace. Sensitive administrator controls remain hidden.",
        "workspace.status": "Setup status",
        "workspace.checklist": "Setup checklist",
        "workspace.next": "Next actions",
        "workspace.next_note": "Some infrastructure tasks are completed together with Repliq support.",
        "workspace.billing": "Billing",
        "workspace.no_tasks": "No setup tasks were returned.",
        "workspace.no_next": "No remaining actions",
        "workspace.progress": "{done} of {total} complete · {percent}%",
        "workspace.workspace_ready": "Workspace ready",
        "workspace.setup_complete": "Setup complete",
        "workspace.public_ready": "Controlled launch ready",
        "workspace.business": "Business profile",
    },
    "lv": {
        "app.name": "Repliq",
        "app.tagline": "AI administratora darba vide",
        "nav.dashboard": "Pārskats",
        "nav.get_started": "Sākt darbu",
        "nav.workspace": "Darba vide",
        "nav.health": "Iestatījumu statuss",
        "nav.account": "Konts",
        "nav.logout": "Izrakstīties",
        "nav.open_menu": "Atvērt izvēlni",
        "nav.aria": "Īpašnieka navigācija",
        "language.label": "Saskarnes valoda",
        "language.lv": "LV",
        "language.ru": "RU",
        "language.en": "EN",
        "common.loading": "Ielādē…",
        "common.load": "Atjaunot",
        "common.open": "Atvērt",
        "common.ready": "Gatavs",
        "common.attention": "Jāpievērš uzmanība",
        "common.complete": "Pabeigts",
        "common.support_controlled": "Kopā ar Repliq atbalstu",
        "common.no_items": "Pagaidām nav datu.",
        "common.technical_details": "Tehniskā informācija",
        "common.secure_area": "Droša īpašnieka zona",
        "common.error": "Radās kļūda.",
        "login.title": "Laipni lūdzam atpakaļ",
        "login.subtitle": "Piesakieties, lai pārvaldītu savu Repliq darba vidi.",
        "login.tenant": "Darba vides ID",
        "login.email": "Īpašnieka e-pasts",
        "login.code": "Piekļuves kods",
        "login.button": "Pieslēgties",
        "login.magic": "Izmantot maģisko saiti",
        "login.note": "Pieslēgšanās izveido drošu īpašnieka sesiju. Šajā lapā netiek rādīti slepenie kodi, hash vērtības vai administratora dati.",
        "login.required": "Ievadiet īpašnieka e-pastu un piekļuves kodu.",
        "login.checking": "Pārbauda datus…",
        "login.success": "Pieslēgšanās veiksmīga. Atver pārskatu…",
        "login.failed": "Neizdevās pieslēgties.",
        "dashboard.title": "Pārskats",
        "dashboard.subtitle": "Uzņēmuma iestatījumi, palaišanas statuss un svarīgākās saites vienuviet.",
        "dashboard.business": "Uzņēmums",
        "dashboard.owner": "Īpašnieka piekļuve",
        "dashboard.scope": "Darba vide",
        "dashboard.scope_value": "Repliq mazajiem uzņēmumiem",
        "dashboard.scope_note": "Droša īpašnieka pārvaldības zona",
        "dashboard.setup": "Iestatīšanas progress",
        "dashboard.setup_note": "Pabeidziet atlikušos soļus pirms palaišanas.",
        "dashboard.auth": "Piekļuves statuss",
        "dashboard.links": "Darba vides rīki",
        "dashboard.tenant": "Darba vides ID",
        "dashboard.session": "Sesijas informācija",
        "dashboard.super_admin": "Atbalsta piekļuve",
        "get_started.badge": "Darba vide ir aktīva",
        "get_started.title": "Pabeigsim Repliq iestatīšanu",
        "get_started.subtitle": "Pārskatiet ieteiktos soļus, aizpildiet uzņēmuma informāciju un veiciet gala pārbaudi.",
        "get_started.open_workspace": "Atvērt darba vidi",
        "get_started.setup_health": "Iestatījumu statuss",
        "get_started.dashboard": "Pārskats",
        "get_started.handoff": "Iestatīšanas pārskats",
        "get_started.next_steps": "Ieteicamie nākamie soļi",
        "get_started.finish": "Pabeigšana un pārbaude",
        "get_started.launch_review": "Gala palaišanas pārbaude",
        "get_started.launch_smoke": "Palaišanas tests",
        "get_started.preview": "Klienta priekšskatījums",
        "get_started.account": "Konts",
        "get_started.status": "Drošs īpašnieka statuss",
        "get_started.handoff_ready": "Pāreja uz iestatīšanu ir gatava",
        "get_started.workspace_complete": "Darba vides iestatīšana pabeigta",
        "get_started.health_complete": "Iestatījumu pārbaude pabeigta",
        "get_started.progress": "Darba vide {done}/{total} · {percent}% · Iestatījumu statuss {health}%",
        "get_started.no_steps": "Iestatīšanas soļi netika atrasti.",
        "get_started.login_required": "Nepieciešama īpašnieka pieslēgšanās.",
        "workspace.title": "Darba vides iestatīšana",
        "workspace.subtitle": "Pārvaldiet galvenos Repliq iestatījumus. Sensitīvie administratora rīki īpašniekam netiek rādīti.",
        "workspace.status": "Iestatījumu statuss",
        "workspace.checklist": "Iestatīšanas saraksts",
        "workspace.next": "Nākamās darbības",
        "workspace.next_note": "Daži infrastruktūras soļi tiek pabeigti kopā ar Repliq atbalstu.",
        "workspace.billing": "Norēķini",
        "workspace.no_tasks": "Iestatīšanas uzdevumi netika atrasti.",
        "workspace.no_next": "Nav atlikušu darbību",
        "workspace.progress": "Pabeigti {done} no {total} · {percent}%",
        "workspace.workspace_ready": "Darba vide gatava",
        "workspace.setup_complete": "Iestatīšana pabeigta",
        "workspace.public_ready": "Kontrolētā palaišana gatava",
        "workspace.business": "Uzņēmuma profils",
    },
    "ru": {
        "app.name": "Repliq",
        "app.tagline": "Рабочий кабинет AI-рецепциониста",
        "nav.dashboard": "Главная",
        "nav.get_started": "Начало работы",
        "nav.workspace": "Рабочая область",
        "nav.health": "Состояние настройки",
        "nav.account": "Аккаунт",
        "nav.logout": "Выйти",
        "nav.open_menu": "Открыть меню",
        "nav.aria": "Навигация владельца",
        "language.label": "Язык интерфейса",
        "language.lv": "LV",
        "language.ru": "RU",
        "language.en": "EN",
        "common.loading": "Загрузка…",
        "common.load": "Обновить",
        "common.open": "Открыть",
        "common.ready": "Готово",
        "common.attention": "Требует внимания",
        "common.complete": "Завершено",
        "common.support_controlled": "Выполняется вместе с поддержкой Repliq",
        "common.no_items": "Пока нечего показывать.",
        "common.technical_details": "Технические детали",
        "common.secure_area": "Защищённая зона владельца",
        "common.error": "Произошла ошибка.",
        "login.title": "С возвращением",
        "login.subtitle": "Войдите, чтобы управлять рабочей областью Repliq.",
        "login.tenant": "ID рабочей области",
        "login.email": "Электронная почта владельца",
        "login.code": "Код входа",
        "login.button": "Войти",
        "login.magic": "Использовать magic link",
        "login.note": "Вход создаёт защищённую сессию владельца. Секретные хеши и административные данные на этой странице не отображаются.",
        "login.required": "Введите электронную почту владельца и код входа.",
        "login.checking": "Проверяем данные…",
        "login.success": "Вход выполнен. Открываем главную страницу…",
        "login.failed": "Не удалось войти.",
        "dashboard.title": "Главная",
        "dashboard.subtitle": "Настройка бизнеса, статус запуска и основные разделы рабочей области в одном месте.",
        "dashboard.business": "Бизнес",
        "dashboard.owner": "Доступ владельца",
        "dashboard.scope": "Рабочая область",
        "dashboard.scope_value": "Repliq для малого бизнеса",
        "dashboard.scope_note": "Безопасная зона управления владельца",
        "dashboard.setup": "Прогресс настройки",
        "dashboard.setup_note": "Завершите оставшиеся шаги перед запуском.",
        "dashboard.auth": "Статус доступа",
        "dashboard.links": "Инструменты рабочей области",
        "dashboard.tenant": "ID рабочей области",
        "dashboard.session": "Данные сессии",
        "dashboard.super_admin": "Доступ поддержки",
        "get_started.badge": "Рабочая область активна",
        "get_started.title": "Завершим настройку Repliq",
        "get_started.subtitle": "Проверьте рекомендуемые шаги, заполните данные бизнеса и выполните финальную проверку запуска.",
        "get_started.open_workspace": "Открыть рабочую область",
        "get_started.setup_health": "Состояние настройки",
        "get_started.dashboard": "Главная",
        "get_started.handoff": "Обзор настройки",
        "get_started.next_steps": "Рекомендуемые следующие шаги",
        "get_started.finish": "Завершение и проверка",
        "get_started.launch_review": "Финальная проверка запуска",
        "get_started.launch_smoke": "Проверка запуска",
        "get_started.preview": "Предпросмотр для клиента",
        "get_started.account": "Аккаунт",
        "get_started.status": "Безопасный статус владельца",
        "get_started.handoff_ready": "Переход к настройке готов",
        "get_started.workspace_complete": "Настройка рабочей области завершена",
        "get_started.health_complete": "Проверка настройки завершена",
        "get_started.progress": "Рабочая область {done}/{total} · {percent}% · Состояние настройки {health}%",
        "get_started.no_steps": "Шаги настройки не найдены.",
        "get_started.login_required": "Требуется вход владельца.",
        "workspace.title": "Настройка рабочей области",
        "workspace.subtitle": "Управляйте основными настройками Repliq. Закрытые административные инструменты владельцу не показываются.",
        "workspace.status": "Состояние настройки",
        "workspace.checklist": "Список настройки",
        "workspace.next": "Следующие действия",
        "workspace.next_note": "Некоторые инфраструктурные задачи выполняются вместе с поддержкой Repliq.",
        "workspace.billing": "Оплата и тариф",
        "workspace.no_tasks": "Задачи настройки не найдены.",
        "workspace.no_next": "Оставшихся действий нет",
        "workspace.progress": "Завершено {done} из {total} · {percent}%",
        "workspace.workspace_ready": "Рабочая область готова",
        "workspace.setup_complete": "Настройка завершена",
        "workspace.public_ready": "Контролируемый запуск готов",
        "workspace.business": "Профиль бизнеса",
    },
}

_KNOWN_LABELS: Dict[str, Dict[str, str]] = {
    "en": {},
    "lv": {
        "Continue setup": "Turpināt iestatīšanu",
        "Review workspace": "Pārskatīt darba vidi",
        "Final launch checklist": "Gala palaišanas pārbaude",
        "SMB launch smoke / demo tenant": "Palaišanas tests / demo vide",
        "Client preview / demo mode": "Klienta priekšskatījums / demo režīms",
        "Conversation insights": "Sarunu analītika",
        "Lead follow-up visibility": "Potenciālo klientu pārraudzība",
        "Edit business profile": "Rediģēt uzņēmuma profilu",
        "Review services": "Pārskatīt pakalpojumus",
        "Edit business memory / FAQ": "Rediģēt zināšanas / BUJ",
        "Review calendar / availability": "Pārskatīt kalendāru / pieejamību",
        "Review Telegram channel": "Pārskatīt Telegram kanālu",
        "Open setup checklist": "Atvērt iestatīšanas sarakstu",
        "Business profile": "Uzņēmuma profils",
        "Services": "Pakalpojumi",
        "Business memory / FAQ": "Uzņēmuma zināšanas / BUJ",
        "Google Calendar / availability": "Google Calendar / pieejamība",
        "Telegram text channel": "Telegram teksta kanāls",
        "Billing / subscription": "Norēķini / abonements",
        "Owner access": "Īpašnieka piekļuve",
        "Self-service launch lock": "Pašapkalpošanās palaišanas statuss",
        "Edit services": "Rediģēt pakalpojumus",
        "Review calendar setup": "Pārskatīt kalendāra iestatījumus",
        "Review calendar": "Pārskatīt kalendāru",
        "Ask Repliq support to finish Telegram setup": "Lūgt Repliq atbalstam pabeigt Telegram iestatīšanu",
        "Review billing": "Pārskatīt norēķinus",
        "Check owner session": "Pārbaudīt īpašnieka sesiju",
        "Review in workspace": "Pārskatīt darba vidē",
        "Open": "Atvērt",
        "Dashboard": "Pārskats",
        "Account": "Konts",
        "Review billing status": "Pārskatīt norēķinu statusu",
        "Account / profile / billing center": "Konta / profila / norēķinu centrs",
        "Setup health / data quality": "Iestatījumu statuss / datu kvalitāte",
        "Readiness lock": "Gatavības statuss",
        "Calendar/channel setup remains controlled by Repliq support in this SMB phase": "Kalendāra un kanālu iestatīšanu šajā posmā pārvalda Repliq atbalsts",
        "Business name, language, timezone and working hours are present.": "Ir norādīts uzņēmuma nosaukums, valoda, laika josla un darba laiks.",
        "Services are available to the receptionist runtime.": "Pakalpojumi ir pieejami AI administratoram.",
        "FAQ/business facts are present for receptionist side-questions.": "AI administratoram ir pieejamas uzņēmuma zināšanas un BUJ.",
        "Google Calendar connection, selected working calendar, timezone and availability are visible in an owner-safe calendar setup screen.": "Google Calendar savienojums, darba kalendārs, laika josla un pieejamība ir redzama īpašnieka kalendāra sadaļā.",
        "Tenant Telegram bot/channel runtime has token/secret and owner-safe channel status metadata.": "Telegram kanāla savienojuma statuss ir pieejams īpašnieka drošajā sadaļā.",
        "Subscription gate allows receptionist runtime for this workspace.": "Abonementa statuss atļauj AI administratora darbību šajā darba vidē.",
        "Owner auth, tenant ownership binding and magic-link foundation are available.": "Īpašnieka autentifikācija un piesaiste darba videi ir gatava.",
        "Stage 78 controlled public self-service SMB MVP launch lock remains ready.": "Kontrolētās SMB palaišanas tehniskais statuss ir gatavs.",
    },
    "ru": {
        "Continue setup": "Продолжить настройку",
        "Review workspace": "Открыть рабочую область",
        "Final launch checklist": "Финальная проверка запуска",
        "SMB launch smoke / demo tenant": "Проверка запуска / демо-среда",
        "Client preview / demo mode": "Предпросмотр / демо-режим",
        "Conversation insights": "Аналитика диалогов",
        "Lead follow-up visibility": "Контроль потенциальных клиентов",
        "Edit business profile": "Редактировать профиль бизнеса",
        "Review services": "Проверить услуги",
        "Edit business memory / FAQ": "Редактировать знания / FAQ",
        "Review calendar / availability": "Проверить календарь / доступность",
        "Review Telegram channel": "Проверить Telegram-канал",
        "Open setup checklist": "Открыть список настройки",
        "Business profile": "Профиль бизнеса",
        "Services": "Услуги",
        "Business memory / FAQ": "Знания бизнеса / FAQ",
        "Google Calendar / availability": "Google Calendar / доступность",
        "Telegram text channel": "Текстовый канал Telegram",
        "Billing / subscription": "Оплата / подписка",
        "Owner access": "Доступ владельца",
        "Self-service launch lock": "Статус самостоятельного запуска",
        "Edit services": "Редактировать услуги",
        "Review calendar setup": "Проверить настройку календаря",
        "Review calendar": "Проверить календарь",
        "Ask Repliq support to finish Telegram setup": "Попросить поддержку Repliq завершить настройку Telegram",
        "Review billing": "Проверить оплату",
        "Check owner session": "Проверить сессию владельца",
        "Review in workspace": "Открыть в рабочей области",
        "Open": "Открыть",
        "Dashboard": "Главная",
        "Account": "Аккаунт",
        "Review billing status": "Проверить оплату и тариф",
        "Account / profile / billing center": "Центр аккаунта, профиля и оплаты",
        "Setup health / data quality": "Состояние настройки и качество данных",
        "Readiness lock": "Статус готовности",
        "Calendar/channel setup remains controlled by Repliq support in this SMB phase": "Настройка календаря и каналов на этом этапе выполняется вместе с поддержкой Repliq",
        "Business name, language, timezone and working hours are present.": "Указаны название бизнеса, язык, часовой пояс и рабочее время.",
        "Services are available to the receptionist runtime.": "Услуги доступны AI-рецепционисту.",
        "FAQ/business facts are present for receptionist side-questions.": "AI-рецепционисту доступны знания о бизнесе и FAQ.",
        "Google Calendar connection, selected working calendar, timezone and availability are visible in an owner-safe calendar setup screen.": "Подключение Google Calendar, рабочий календарь, часовой пояс и доступность видны в безопасном разделе владельца.",
        "Tenant Telegram bot/channel runtime has token/secret and owner-safe channel status metadata.": "Статус подключения Telegram-канала доступен в безопасном разделе владельца.",
        "Subscription gate allows receptionist runtime for this workspace.": "Статус подписки разрешает работу AI-рецепциониста в этой рабочей области.",
        "Owner auth, tenant ownership binding and magic-link foundation are available.": "Аутентификация владельца и привязка к рабочей области готовы.",
        "Stage 78 controlled public self-service SMB MVP launch lock remains ready.": "Технический статус контролируемого запуска SMB готов.",
    },
}

CX1_UI_CSS = r"""
:root{--rq-bg:#f4f7fb;--rq-surface:#fff;--rq-surface-soft:#f8fafc;--rq-text:#152033;--rq-muted:#667085;--rq-border:#e3e8ef;--rq-primary:#5b47e0;--rq-primary-dark:#4433bd;--rq-primary-soft:#efedff;--rq-success:#067647;--rq-success-bg:#ecfdf3;--rq-warning:#b54708;--rq-warning-bg:#fffaeb;--rq-danger:#b42318;--rq-danger-bg:#fef3f2;--rq-shadow:0 12px 35px rgba(31,42,68,.08);--rq-radius:18px;--rq-radius-sm:12px;--rq-max:1180px}
*{box-sizing:border-box}html{background:var(--rq-bg)}body.rq-body{margin:0;background:radial-gradient(circle at 15% -10%,rgba(91,71,224,.12),transparent 28rem),var(--rq-bg);color:var(--rq-text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}a{color:inherit}.rq-shell{min-height:100vh}.rq-topbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.88);backdrop-filter:blur(16px);border-bottom:1px solid rgba(227,232,239,.9)}.rq-topbar-inner{max-width:var(--rq-max);margin:0 auto;min-height:72px;padding:0 22px;display:flex;align-items:center;gap:22px}.rq-brand{display:flex;align-items:center;gap:11px;text-decoration:none;min-width:max-content}.rq-logo{width:38px;height:38px;border-radius:12px;background:linear-gradient(145deg,#735cff,#4935c5);display:grid;place-items:center;color:#fff;font-size:20px;font-weight:900;box-shadow:0 8px 20px rgba(91,71,224,.28)}.rq-brand-name{font-size:17px;font-weight:850;line-height:1}.rq-brand-tagline{font-size:11px;color:var(--rq-muted);margin-top:4px}.rq-nav{display:flex;align-items:center;gap:4px;flex:1}.rq-nav a{padding:9px 11px;border-radius:10px;text-decoration:none;color:#475467;font-size:13px;font-weight:700;white-space:nowrap}.rq-nav a:hover{background:#f2f4f7;color:var(--rq-text)}.rq-nav a.active{background:var(--rq-primary-soft);color:var(--rq-primary)}.rq-top-actions{display:flex;align-items:center;gap:10px;margin-left:auto}.rq-lang{display:flex;background:#f2f4f7;padding:3px;border-radius:11px}.rq-lang button{border:0;background:transparent;color:#667085;padding:7px 8px;border-radius:8px;font-size:12px;font-weight:800;cursor:pointer}.rq-lang button.active{background:#fff;color:var(--rq-primary);box-shadow:0 1px 4px rgba(16,24,40,.12)}.rq-logout{font-size:13px;font-weight:750;text-decoration:none;color:#475467}.rq-menu-button{display:none;border:1px solid var(--rq-border);background:#fff;width:40px;height:40px;border-radius:11px;font-size:18px;cursor:pointer}.rq-mobile-nav{display:none;max-width:var(--rq-max);margin:0 auto;padding:0 16px 14px}.rq-mobile-nav.open{display:grid;grid-template-columns:1fr 1fr;gap:7px}.rq-mobile-nav a{padding:11px;border:1px solid var(--rq-border);background:#fff;border-radius:10px;text-decoration:none;font-size:13px;font-weight:700}.rq-main{max-width:var(--rq-max);margin:0 auto;padding:30px 22px 54px}.rq-auth-main{max-width:560px;padding-top:7vh}.rq-page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:22px}.rq-eyebrow{display:inline-flex;align-items:center;gap:7px;color:var(--rq-primary);background:var(--rq-primary-soft);border-radius:999px;padding:6px 10px;font-size:12px;font-weight:850;margin-bottom:12px}.rq-page-title{font-size:clamp(30px,4vw,46px);line-height:1.04;letter-spacing:-.04em;margin:0}.rq-page-subtitle{max-width:720px;color:var(--rq-muted);font-size:15px;line-height:1.6;margin:12px 0 0}.rq-card{background:var(--rq-surface);border:1px solid var(--rq-border);border-radius:var(--rq-radius);box-shadow:var(--rq-shadow);padding:20px}.rq-card+.rq-card{margin-top:14px}.rq-card-title{font-size:18px;margin:0 0 12px;letter-spacing:-.02em}.rq-card-subtitle{color:var(--rq-muted);font-size:13px;line-height:1.5}.rq-grid{display:grid;gap:14px}.rq-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.rq-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}.rq-stat{min-height:145px}.rq-stat-label{font-size:12px;color:var(--rq-muted);font-weight:750;text-transform:uppercase;letter-spacing:.05em}.rq-stat-value{font-size:23px;font-weight:850;margin-top:10px}.rq-stat-note{font-size:13px;color:var(--rq-muted);margin-top:7px;line-height:1.45}.rq-actions{display:flex;flex-wrap:wrap;gap:9px;align-items:center}.rq-button{appearance:none;border:0;border-radius:11px;padding:10px 14px;background:var(--rq-primary);color:#fff;font-weight:800;font-size:13px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:7px}.rq-button:hover{background:var(--rq-primary-dark)}.rq-button-secondary{background:#eef1f6;color:#344054}.rq-button-secondary:hover{background:#e4e8ef}.rq-button-ghost{background:transparent;color:#475467;border:1px solid var(--rq-border)}.rq-button-ghost:hover{background:#f8fafc}.rq-field{display:grid;gap:7px;margin-top:14px}.rq-label{font-size:13px;font-weight:750;color:#344054}.rq-input{width:100%;border:1px solid #d0d5dd;border-radius:11px;padding:12px 13px;background:#fff;color:var(--rq-text);font-size:14px;outline:none}.rq-input:focus{border-color:#8b7cf6;box-shadow:0 0 0 4px rgba(91,71,224,.12)}.rq-inline-field{display:flex;gap:8px;align-items:center}.rq-inline-field .rq-input{min-width:220px}.rq-badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;background:#eef1f6;color:#475467;font-size:11px;font-weight:850;margin:2px 4px 2px 0}.rq-badge-success{background:var(--rq-success-bg);color:var(--rq-success)}.rq-badge-warning{background:var(--rq-warning-bg);color:var(--rq-warning)}.rq-badge-danger{background:var(--rq-danger-bg);color:var(--rq-danger)}.rq-progress{height:9px;border-radius:99px;background:#eef1f6;overflow:hidden;margin-top:12px}.rq-progress>span{height:100%;display:block;background:linear-gradient(90deg,#5b47e0,#8d75ff);border-radius:inherit;transition:width .25s ease}.rq-task{border:1px solid var(--rq-border);border-radius:15px;padding:16px;background:linear-gradient(180deg,#fff,#fbfcfe)}.rq-task h3{margin:0 0 7px;font-size:16px}.rq-muted{color:var(--rq-muted);font-size:13px;line-height:1.5}.rq-notice{border-radius:12px;padding:11px 13px;font-size:13px;margin-top:13px}.rq-notice[hidden]{display:none}.rq-notice-success{background:var(--rq-success-bg);color:var(--rq-success);border:1px solid #abefc6}.rq-notice-error{background:var(--rq-danger-bg);color:var(--rq-danger);border:1px solid #fecdca}.rq-details{margin-top:14px;border:1px solid var(--rq-border);border-radius:14px;background:#fff;overflow:hidden}.rq-details summary{padding:13px 15px;cursor:pointer;font-weight:750;color:#475467}.rq-details pre{margin:0;border-top:1px solid var(--rq-border);background:#101828;color:#e4e7ec;padding:15px;max-height:420px;overflow:auto;white-space:pre-wrap;font-size:12px}.rq-auth-card{padding:28px}.rq-auth-brand{text-align:center;margin-bottom:22px}.rq-auth-brand .rq-logo{margin:0 auto 12px}.rq-security-note{display:flex;gap:9px;align-items:flex-start;margin-top:18px;background:#f8fafc;border:1px solid var(--rq-border);padding:12px;border-radius:12px;color:#667085;font-size:12px;line-height:1.45}.rq-section{margin-top:16px}.rq-spacer{height:14px}.rq-footer{max-width:var(--rq-max);margin:0 auto;padding:0 22px 28px;color:#98a2b3;font-size:11px;text-align:center}
@media(max-width:980px){.rq-nav,.rq-logout{display:none}.rq-menu-button{display:block}.rq-grid-3{grid-template-columns:1fr 1fr}.rq-topbar-inner{padding:0 16px}.rq-main{padding:24px 16px 44px}}
@media(max-width:680px){.rq-brand-tagline{display:none}.rq-topbar-inner{gap:10px}.rq-lang button{padding:7px}.rq-grid-2,.rq-grid-3{grid-template-columns:1fr}.rq-page-head{display:block}.rq-page-title{font-size:32px}.rq-card{padding:16px}.rq-auth-card{padding:21px}.rq-inline-field{display:grid}.rq-inline-field .rq-input{min-width:0}.rq-mobile-nav.open{grid-template-columns:1fr}.rq-main{padding-top:20px}}
"""

CX1_UI_JS = r"""
(function(){
  const cookieName='repliq_ui_lang';
  function setCookie(value){const secure=location.protocol==='https:'?'; Secure':'';document.cookie=cookieName+'='+encodeURIComponent(value)+'; Path=/; Max-Age=31536000; SameSite=Lax'+secure;}
  function changeLanguage(lang){if(!['lv','ru','en'].includes(lang))return;setCookie(lang);const url=new URL(window.location.href);url.searchParams.set('ui_lang',lang);window.location=url.toString();}
  document.querySelectorAll('[data-rq-lang]').forEach(function(btn){btn.addEventListener('click',function(){changeLanguage(btn.getAttribute('data-rq-lang'));});});
  const menu=document.querySelector('[data-rq-mobile-menu]');const panel=document.querySelector('[data-rq-mobile-nav]');if(menu&&panel){menu.addEventListener('click',function(){panel.classList.toggle('open');menu.setAttribute('aria-expanded',panel.classList.contains('open')?'true':'false');});}
  window.RepliqUI={
    changeLanguage:changeLanguage,
    esc:function(v){return v===null||v===undefined?'':String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');},
    go:function(path){window.location=path;},
    clampPercent:function(value){const n=Number(value||0);return Math.max(0,Math.min(100,Number.isFinite(n)?n:0));}
  };
})();
"""


def normalize_ui_language(value: Any, default: str = UI_DEFAULT_LANGUAGE) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if raw.startswith("lv"):
        return "lv"
    if raw.startswith("ru"):
        return "ru"
    if raw.startswith("en"):
        return "en"
    return default if default in UI_SUPPORTED_LANGUAGES else UI_DEFAULT_LANGUAGE


def resolve_ui_language(request: Any = None, default: str = UI_DEFAULT_LANGUAGE) -> str:
    if request is not None:
        try:
            query_value = request.query_params.get("ui_lang")
        except Exception:
            query_value = None
        if query_value:
            return normalize_ui_language(query_value, default)
        try:
            cookie_value = request.cookies.get(UI_LANG_COOKIE)
        except Exception:
            cookie_value = None
        if cookie_value:
            return normalize_ui_language(cookie_value, default)
        try:
            accept_language = request.headers.get("accept-language", "")
        except Exception:
            accept_language = ""
        if accept_language:
            return normalize_ui_language(accept_language.split(",", 1)[0], default)
    return normalize_ui_language(default, UI_DEFAULT_LANGUAGE)


def ui_text(lang: str, key: str, **values: Any) -> str:
    normalized = normalize_ui_language(lang)
    value = _UI_TEXT.get(normalized, {}).get(key) or _UI_TEXT["en"].get(key) or key
    if values:
        try:
            return value.format(**values)
        except Exception:
            return value
    return value


def ui_strings(lang: str, keys: Iterable[str]) -> Dict[str, str]:
    return {key: ui_text(lang, key) for key in keys}


def ui_known_labels(lang: str) -> Dict[str, str]:
    normalized = normalize_ui_language(lang)
    return dict(_KNOWN_LABELS.get(normalized, {}))


def render_repliq_shell(
    *,
    title: str,
    lang: str,
    tenant_id: str,
    content_html: str,
    active_nav: str = "",
    owner_navigation: bool = True,
    auth_layout: bool = False,
    inline_script: str = "",
    extra_head: str = "",
) -> str:
    normalized = normalize_ui_language(lang)
    tenant = str(tenant_id or "").strip() or "clinic_demo"
    tenant_q = html.escape(urllib.parse.quote(tenant, safe="_-"), quote=True)
    nav_items = [
        ("dashboard", ui_text(normalized, "nav.dashboard"), f"/owner/dashboard/ui?tenant_id={tenant_q}"),
        ("get_started", ui_text(normalized, "nav.get_started"), f"/owner/get-started/ui?tenant_id={tenant_q}"),
        ("workspace", ui_text(normalized, "nav.workspace"), f"/owner/workspace/ui?tenant_id={tenant_q}"),
        ("health", ui_text(normalized, "nav.health"), f"/owner/setup-health/ui?tenant_id={tenant_q}"),
        ("account", ui_text(normalized, "nav.account"), f"/owner/account/ui?tenant_id={tenant_q}"),
    ]
    nav_html = "".join(
        f'<a class="{"active" if key == active_nav else ""}" href="{href}">{html.escape(label)}</a>'
        for key, label, href in nav_items
    ) if owner_navigation else ""
    mobile_nav_html = nav_html + (f'<a href="/owner/logout">{html.escape(ui_text(normalized,"nav.logout"))}</a>' if owner_navigation else "")
    lang_buttons = "".join(
        f'<button type="button" class="{"active" if code == normalized else ""}" data-rq-lang="{code}" aria-label="{html.escape(ui_text(normalized,"language.label"))}: {code.upper()}">{html.escape(ui_text(normalized,f"language.{code}"))}</button>'
        for code in UI_SUPPORTED_LANGUAGES
    )
    topbar = f'''
<header class="rq-topbar">
  <div class="rq-topbar-inner">
    <a class="rq-brand" href="{'/owner/dashboard/ui?tenant_id='+tenant_q if owner_navigation else '/launch'}">
      <span class="rq-logo">R</span><span><span class="rq-brand-name">{html.escape(ui_text(normalized,'app.name'))}</span><span class="rq-brand-tagline">{html.escape(ui_text(normalized,'app.tagline'))}</span></span>
    </a>
    <nav class="rq-nav" aria-label="{html.escape(ui_text(normalized,'nav.aria'))}">{nav_html}</nav>
    <div class="rq-top-actions">
      <div class="rq-lang" aria-label="{html.escape(ui_text(normalized,'language.label'))}">{lang_buttons}</div>
      {f'<a class="rq-logout" href="/owner/logout">{html.escape(ui_text(normalized,"nav.logout"))}</a>' if owner_navigation else ''}
      {f'<button class="rq-menu-button" type="button" data-rq-mobile-menu aria-expanded="false" aria-label="{html.escape(ui_text(normalized,"nav.open_menu"))}">☰</button>' if owner_navigation else ''}
    </div>
  </div>
  {f'<nav class="rq-mobile-nav" data-rq-mobile-nav>{mobile_nav_html}</nav>' if owner_navigation else ''}
</header>'''
    main_class = "rq-main rq-auth-main" if auth_layout else "rq-main"
    script = f'<script src="/assets/repliq-ui.js?v={UI_FOUNDATION_VERSION}"></script>'
    if inline_script:
        script += f"<script>{inline_script}</script>"
    return f'''<!doctype html>
<html lang="{normalized}">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta name="color-scheme" content="light"/>
  <title>{html.escape(title)} · Repliq</title>
  <link rel="stylesheet" href="/assets/repliq-ui.css?v={UI_FOUNDATION_VERSION}"/>
  {extra_head}
</head>
<body class="rq-body" data-rq-ui-lang="{normalized}" data-rq-ui-version="{UI_FOUNDATION_VERSION}">
<div class="rq-shell">{topbar}<main class="{main_class}">{content_html}</main><footer class="rq-footer">Repliq · {UI_FOUNDATION_VERSION}</footer></div>
{script}
</body></html>'''
