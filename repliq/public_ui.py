from __future__ import annotations

import html
import json
import urllib.parse
from typing import Any, Dict, Iterable, Optional

from repliq.ui_foundation import (
    UI_FOUNDATION_VERSION,
    UI_LANG_COOKIE,
    UI_SUPPORTED_LANGUAGES,
    normalize_ui_language,
    resolve_ui_language,
)

CX3_PUBLIC_UI_VERSION = "cx3.1"

_PUBLIC_TEXT: Dict[str, Dict[str, str]] = {
    "en": {
        "meta.home": "Repliq — AI receptionist for small and medium businesses",
        "meta.home_desc": "Repliq helps small businesses answer customer messages, explain services and support booking workflows from one owner workspace.",
        "meta.signup": "Create your Repliq workspace",
        "meta.login": "Owner login — Repliq",
        "meta.magic": "Magic link login — Repliq",
        "meta.privacy": "Privacy — Repliq",
        "meta.terms": "Terms — Repliq",
        "meta.contact": "Contact — Repliq",
        "meta.support": "Support — Repliq",
        "brand.tagline": "AI receptionist for everyday customer conversations",
        "nav.product": "Product",
        "nav.how": "How it works",
        "nav.security": "Safety",
        "nav.support": "Support",
        "nav.login": "Owner login",
        "nav.signup": "Create workspace",
        "nav.open": "Open menu",
        "nav.language": "Language",
        "footer.product": "Product",
        "footer.company": "Information",
        "footer.account": "Account",
        "footer.home": "Home",
        "footer.signup": "Create workspace",
        "footer.login": "Owner login",
        "footer.privacy": "Privacy",
        "footer.terms": "Terms",
        "footer.contact": "Contact",
        "footer.support": "Support",
        "footer.note": "Repliq is currently offered as a controlled SMB service. Availability and integrations depend on workspace configuration.",
        "home.eyebrow": "Customer communication, organised",
        "home.title": "A practical AI receptionist for messages, FAQs and bookings.",
        "home.lead": "Repliq helps a business respond consistently, guide customers through services and booking, and keep the owner in control from one workspace.",
        "home.cta": "Create a workspace",
        "home.login": "Open owner account",
        "home.scope": "Text-first SMB product",
        "home.scope_note": "Designed for controlled onboarding and real business configuration — without pretending every channel or payment flow is automatic.",
        "home.problem_kicker": "The daily problem",
        "home.problem_title": "Customer questions arrive while the team is busy.",
        "home.problem_text": "Prices, opening hours, availability and booking changes repeat across the day. Repliq keeps those answers connected to the business settings instead of relying on scattered notes.",
        "home.feature1_title": "Answer routine questions",
        "home.feature1_text": "Use the configured service catalog and business knowledge to answer common customer questions in the supported languages.",
        "home.feature2_title": "Support booking workflows",
        "home.feature2_text": "Guide booking, rescheduling and cancellation through the existing controlled calendar workflow.",
        "home.feature3_title": "Keep the owner informed",
        "home.feature3_text": "Review setup health, conversation insights, follow-up candidates and launch readiness from the owner workspace.",
        "home.how_kicker": "How it works",
        "home.how_title": "From business setup to customer conversations.",
        "home.step1": "Create the workspace",
        "home.step1_text": "Add the business name, owner email, working hours, timezone and primary customer language.",
        "home.step2": "Configure the business",
        "home.step2_text": "Add services, prices, FAQ, policies, calendar availability and the communication channel used for the pilot.",
        "home.step3": "Preview and launch",
        "home.step3_text": "Test answers in safe preview mode, review launch health and then enable the agreed customer flow.",
        "home.control_kicker": "Owner control",
        "home.control_title": "AI handles the conversation. The business keeps the rules.",
        "home.control_text": "Repliq uses the configured catalog, business memory and availability. Owner pages expose setup and conversation visibility without exposing internal secrets to the client account.",
        "home.control1": "Separate owner and administrator access",
        "home.control2": "Safe preview without calendar writes or external messages",
        "home.control3": "Read-only analytics and follow-up visibility",
        "home.control4": "LV, RU and EN owner interface",
        "home.safety_kicker": "Safety by design",
        "home.safety_title": "Controlled actions instead of an unrestricted chatbot.",
        "home.safety_text": "The language model helps understand customer intent. Booking and other business actions remain in the application workflow, with tenant boundaries, access controls and readiness checks.",
        "home.audience_kicker": "Built for service businesses",
        "home.audience_title": "A flexible foundation for clinics, salons and other appointment-led teams.",
        "home.audience_text": "The workspace supports configurable services, business knowledge, hours, language and channels. Each launch is based on the actual tenant setup rather than a generic demo promise.",
        "home.final_title": "Start with a controlled workspace.",
        "home.final_text": "Create an owner account, complete the setup checklist and preview the customer experience before going live.",
        "signup.eyebrow": "Workspace creation",
        "signup.title": "Create your Repliq workspace",
        "signup.lead": "Start the owner workspace with the essential business details. You can complete services, FAQ, calendar and channel setup after signup.",
        "signup.business": "Business name",
        "signup.slug": "Workspace identifier",
        "signup.slug_help": "A short technical identifier. It is suggested from the business name and can be adjusted before creation.",
        "signup.email": "Owner email",
        "signup.phone": "Business phone",
        "signup.type": "Business type",
        "signup.language": "Primary customer language",
        "signup.language_help": "This controls the initial business language, not the language of this website.",
        "signup.timezone": "Timezone",
        "signup.hours": "Working hours",
        "signup.start": "Start",
        "signup.end": "End",
        "signup.terms_prefix": "I confirm this is a real business request and accept the",
        "signup.terms_link": "Terms",
        "signup.privacy_link": "Privacy notice",
        "signup.button": "Create workspace",
        "signup.creating": "Creating workspace…",
        "signup.required": "Business name and owner email are required.",
        "signup.confirm": "Please accept the Terms and Privacy notice.",
        "signup.failed": "Workspace creation failed.",
        "signup.success": "Workspace created. Your owner session is active.",
        "signup.result_title": "Your workspace is ready",
        "signup.result_tenant": "Workspace",
        "signup.result_owner": "Owner",
        "signup.result_session": "Owner session created",
        "signup.result_next": "Continue to the private setup checklist to configure the business.",
        "signup.continue": "Continue setup",
        "signup.copy": "Copy backup login code",
        "signup.code_note": "Store the backup login code securely. It is shown once. Do not share login codes or magic links in support chats.",
        "signup.details": "Technical signup details",
        "signup.readiness": "Controlled public signup is available",
        "login.eyebrow": "Owner account",
        "login.title": "Sign in to your workspace",
        "login.lead": "Use the workspace identifier, owner email and backup login code created during onboarding.",
        "login.tenant": "Workspace identifier",
        "login.email": "Owner email",
        "login.code": "Login code",
        "login.button": "Sign in",
        "login.magic": "Use a magic link token",
        "login.required": "Owner email and login code are required.",
        "login.checking": "Checking your account…",
        "login.success": "Login successful. Opening the workspace…",
        "login.failed": "Login failed.",
        "login.note": "The session is stored in a secure browser cookie. The workspace identifier alone does not grant access.",
        "magic.eyebrow": "One-time access",
        "magic.title": "Sign in with a magic link",
        "magic.lead": "Open the full magic link directly, or paste the one-time token below. The token expires and cannot be reused.",
        "magic.tenant": "Workspace identifier",
        "magic.token": "Magic token",
        "magic.button": "Sign in with token",
        "magic.required": "Magic token is required.",
        "magic.checking": "Checking the token…",
        "magic.success": "Login successful. Opening the workspace…",
        "magic.failed": "Magic login failed.",
        "magic.note": "Tokens are stored only as hashes and set the same private owner session after successful verification.",
        "logout.eyebrow": "Session closed",
        "logout.title": "You are signed out",
        "logout.text": "Owner and administrator browser sessions were cleared on this device.",
        "logout.login": "Sign in again",
        "logout.home": "Return to website",
        "legal.updated": "Product notice for the current controlled service phase",
        "privacy.title": "Privacy notice",
        "privacy.lead": "This page explains the main categories of information processed by Repliq during workspace signup, owner use and customer conversations.",
        "privacy.s1": "Information we process",
        "privacy.s1_text": "Workspace and owner details, configured business information, authentication and security events, customer conversation content, booking-related data and technical logs needed to operate and protect the service.",
        "privacy.s2": "Why it is used",
        "privacy.s2_text": "To create and secure workspaces, provide receptionist and booking functions, connect configured channels and calendars, show owner analytics, prevent abuse and troubleshoot the service.",
        "privacy.s3": "Service providers",
        "privacy.s3_text": "The service may use configured hosting, AI, messaging, email and calendar providers. The exact providers and enabled integrations depend on the workspace deployment and pilot agreement.",
        "privacy.s4": "Cookies and browser storage",
        "privacy.s4_text": "Repliq uses necessary cookies for owner and administrator sessions, CSRF protection and the selected interface language. It does not use advertising cookies in the current product.",
        "privacy.s5": "Retention and access",
        "privacy.s5_text": "Retention depends on the data type, workspace configuration and operational requirements. Access is limited through tenant and role boundaries. Owners should avoid entering unnecessary sensitive information into business knowledge or test conversations.",
        "privacy.s6": "Requests and contact",
        "privacy.s6_text": "For access, correction or deletion questions, use the configured Repliq support contact or the contact channel provided during onboarding. Identity and workspace access may need to be verified.",
        "privacy.disclaimer": "Before a broad commercial launch, the operator should have this notice reviewed and completed with the legal entity, controller contact, retention periods and subprocessors applicable to the final deployment.",
        "terms.title": "Service terms",
        "terms.lead": "These terms describe the current controlled Repliq workspace service and do not replace a signed pilot or commercial agreement where one exists.",
        "terms.s1": "Service scope",
        "terms.s1_text": "Repliq provides a configurable owner workspace and AI-assisted customer communication flows. Available channels, calendar functions, billing and support depend on the workspace configuration.",
        "terms.s2": "Owner responsibilities",
        "terms.s2_text": "The owner is responsible for accurate business details, services, prices, policies, availability, lawful customer communications and appropriate access to the owner account.",
        "terms.s3": "AI and automation",
        "terms.s3_text": "Automated replies can be imperfect. The business should review configuration and preview important flows. Repliq does not guarantee that every message will be understood or that every external provider will be continuously available.",
        "terms.s4": "Accounts and security",
        "terms.s4_text": "Login codes, magic links and sessions must be kept private. Access may be limited or suspended to protect the service, investigate abuse or comply with legal obligations.",
        "terms.s5": "Plans and payment",
        "terms.s5_text": "The current product supports controlled subscription status and manual billing foundations. Price, trial and payment terms are defined in the applicable offer or agreement; this website does not promise automated checkout.",
        "terms.s6": "Availability and changes",
        "terms.s6_text": "Features may change during the controlled product phase. Material operational changes should be communicated through the agreed owner or support channel.",
        "terms.s7": "Limitation",
        "terms.s7_text": "The service is not a substitute for professional medical, legal, financial or emergency advice. The business remains responsible for customer-facing decisions and for reviewing high-impact situations.",
        "terms.disclaimer": "These product terms require legal review and completion with the operating entity, governing law, liability limits, cancellation rules and commercial terms before broad public sales.",
        "contact.title": "Contact Repliq",
        "contact.lead": "Choose the path that matches your situation. Contact details can be configured for the final commercial deployment without exposing private administrator channels.",
        "contact.new_title": "New workspace",
        "contact.new_text": "Create a controlled workspace and continue through the guided owner setup.",
        "contact.owner_title": "Existing owner",
        "contact.owner_text": "Sign in to review setup, account information and the available support context for your workspace.",
        "contact.direct_title": "Direct contact",
        "contact.direct_text": "A public contact email has not been configured for this deployment. Pilot contact details are provided during onboarding.",
        "contact.email_label": "Email us",
        "support.title": "Repliq support",
        "support.lead": "Start with the owner workspace so the request stays connected to the correct tenant and configuration.",
        "support.s1": "Cannot sign in",
        "support.s1_text": "Check the workspace identifier and owner email. Use the backup login code or a valid one-time magic link. Do not post credentials in chat messages.",
        "support.s2": "Setup or channel issue",
        "support.s2_text": "Open Setup Health, Calendar or Telegram in the owner workspace and note the visible status without sharing tokens or raw secrets.",
        "support.s3": "Unexpected customer reply",
        "support.s3_text": "Record the tenant, channel, approximate time and customer wording. Avoid including unnecessary personal information when reporting the example.",
        "support.s4": "Booking or calendar issue",
        "support.s4_text": "Check the selected calendar, availability and service duration. Use preview mode first because live booking tests may create or modify calendar events.",
        "support.cta": "Open owner login",
        "common.back_home": "Back to home",
        "common.open_signup": "Create workspace",
        "common.open_login": "Owner login",
        "common.yes": "Yes",
        "common.no": "No",
        "common.loading": "Loading…",
    },
    "ru": {
        "meta.home": "Repliq — AI-рецепционист для малого и среднего бизнеса",
        "meta.home_desc": "Repliq помогает бизнесу отвечать на сообщения клиентов, объяснять услуги и поддерживать запись из единого кабинета владельца.",
        "meta.signup": "Создать рабочее пространство Repliq",
        "meta.login": "Вход владельца — Repliq",
        "meta.magic": "Вход по magic link — Repliq",
        "meta.privacy": "Конфиденциальность — Repliq",
        "meta.terms": "Условия — Repliq",
        "meta.contact": "Контакты — Repliq",
        "meta.support": "Поддержка — Repliq",
        "brand.tagline": "AI-рецепционист для ежедневного общения с клиентами",
        "nav.product": "Продукт",
        "nav.how": "Как это работает",
        "nav.security": "Безопасность",
        "nav.support": "Поддержка",
        "nav.login": "Вход владельца",
        "nav.signup": "Создать кабинет",
        "nav.open": "Открыть меню",
        "nav.language": "Язык",
        "footer.product": "Продукт",
        "footer.company": "Информация",
        "footer.account": "Аккаунт",
        "footer.home": "Главная",
        "footer.signup": "Создать кабинет",
        "footer.login": "Вход владельца",
        "footer.privacy": "Конфиденциальность",
        "footer.terms": "Условия",
        "footer.contact": "Контакты",
        "footer.support": "Поддержка",
        "footer.note": "Сейчас Repliq предоставляется как контролируемый SMB-сервис. Доступность функций и интеграций зависит от настройки конкретного кабинета.",
        "home.eyebrow": "Общение с клиентами — в порядке",
        "home.title": "Практичный AI-рецепционист для сообщений, FAQ и записи.",
        "home.lead": "Repliq помогает бизнесу отвечать последовательно, знакомить клиентов с услугами и вести их к записи, сохраняя контроль у владельца.",
        "home.cta": "Создать кабинет",
        "home.login": "Открыть аккаунт владельца",
        "home.scope": "Текстовый SMB-продукт",
        "home.scope_note": "Для контролируемого подключения и реальной настройки бизнеса — без обещаний, что каждый канал или платёж уже полностью автоматизирован.",
        "home.problem_kicker": "Ежедневная проблема",
        "home.problem_title": "Вопросы клиентов приходят, пока команда занята.",
        "home.problem_text": "Цены, часы работы, свободное время и перенос записи повторяются каждый день. Repliq связывает ответы с настройками бизнеса, а не с разрозненными заметками.",
        "home.feature1_title": "Ответы на типовые вопросы",
        "home.feature1_text": "Используйте каталог услуг и знания бизнеса для ответов на частые вопросы клиентов на поддерживаемых языках.",
        "home.feature2_title": "Поддержка записи",
        "home.feature2_text": "Ведите клиента через запись, перенос и отмену в рамках существующего контролируемого календарного процесса.",
        "home.feature3_title": "Контроль для владельца",
        "home.feature3_text": "Проверяйте состояние настройки, аналитику диалогов, кандидатов для повторного контакта и готовность к запуску.",
        "home.how_kicker": "Как это работает",
        "home.how_title": "От настройки бизнеса до диалогов с клиентами.",
        "home.step1": "Создайте кабинет",
        "home.step1_text": "Укажите название бизнеса, email владельца, часы работы, часовой пояс и основной язык клиентов.",
        "home.step2": "Настройте бизнес",
        "home.step2_text": "Добавьте услуги, цены, FAQ, правила, доступность календаря и канал связи для пилота.",
        "home.step3": "Проверьте и запустите",
        "home.step3_text": "Протестируйте ответы в безопасном preview, проверьте готовность и включите согласованный клиентский поток.",
        "home.control_kicker": "Контроль владельца",
        "home.control_title": "AI ведёт диалог. Правила остаются у бизнеса.",
        "home.control_text": "Repliq использует настроенный каталог, знания бизнеса и доступность. Кабинет показывает состояние и диалоги, не раскрывая внутренние секреты клиентскому аккаунту.",
        "home.control1": "Раздельный доступ владельца и администратора",
        "home.control2": "Безопасный preview без записей в календарь и внешних сообщений",
        "home.control3": "Аналитика и follow-up только для чтения",
        "home.control4": "Интерфейс владельца на LV, RU и EN",
        "home.safety_kicker": "Безопасность по архитектуре",
        "home.safety_title": "Контролируемые действия вместо неограниченного чат-бота.",
        "home.safety_text": "Языковая модель помогает понять намерение клиента. Запись и другие действия остаются в workflow приложения с tenant-границами, контролем доступа и readiness-проверками.",
        "home.audience_kicker": "Для сервисного бизнеса",
        "home.audience_title": "Гибкая основа для клиник, салонов и других команд, работающих по записи.",
        "home.audience_text": "Кабинет поддерживает настраиваемые услуги, знания, часы, язык и каналы. Каждый запуск опирается на реальные настройки tenant, а не на обещания демо.",
        "home.final_title": "Начните с контролируемого кабинета.",
        "home.final_text": "Создайте аккаунт владельца, завершите checklist и проверьте клиентский опыт до запуска.",
        "signup.eyebrow": "Создание кабинета",
        "signup.title": "Создайте рабочее пространство Repliq",
        "signup.lead": "Начните с основных данных бизнеса. Услуги, FAQ, календарь и канал можно настроить после регистрации.",
        "signup.business": "Название бизнеса",
        "signup.slug": "Идентификатор кабинета",
        "signup.slug_help": "Короткий технический идентификатор. Он предлагается из названия бизнеса и может быть изменён до создания.",
        "signup.email": "Email владельца",
        "signup.phone": "Телефон бизнеса",
        "signup.type": "Тип бизнеса",
        "signup.language": "Основной язык клиентов",
        "signup.language_help": "Это начальный язык бизнеса, а не язык этого сайта.",
        "signup.timezone": "Часовой пояс",
        "signup.hours": "Рабочие часы",
        "signup.start": "Начало",
        "signup.end": "Конец",
        "signup.terms_prefix": "Я подтверждаю реальный запрос бизнеса и принимаю",
        "signup.terms_link": "Условия",
        "signup.privacy_link": "Уведомление о конфиденциальности",
        "signup.button": "Создать кабинет",
        "signup.creating": "Создаём кабинет…",
        "signup.required": "Название бизнеса и email владельца обязательны.",
        "signup.confirm": "Примите Условия и уведомление о конфиденциальности.",
        "signup.failed": "Не удалось создать кабинет.",
        "signup.success": "Кабинет создан. Сессия владельца активна.",
        "signup.result_title": "Ваш кабинет готов",
        "signup.result_tenant": "Кабинет",
        "signup.result_owner": "Владелец",
        "signup.result_session": "Сессия владельца создана",
        "signup.result_next": "Перейдите к закрытому checklist и завершите настройку бизнеса.",
        "signup.continue": "Продолжить настройку",
        "signup.copy": "Скопировать резервный код",
        "signup.code_note": "Храните резервный код безопасно. Он показывается один раз. Не отправляйте коды и magic links в чат поддержки.",
        "signup.details": "Технические данные регистрации",
        "signup.readiness": "Контролируемая публичная регистрация доступна",
        "login.eyebrow": "Аккаунт владельца",
        "login.title": "Войдите в рабочее пространство",
        "login.lead": "Используйте идентификатор кабинета, email владельца и резервный код, созданный при подключении.",
        "login.tenant": "Идентификатор кабинета",
        "login.email": "Email владельца",
        "login.code": "Код входа",
        "login.button": "Войти",
        "login.magic": "Использовать magic token",
        "login.required": "Email владельца и код входа обязательны.",
        "login.checking": "Проверяем аккаунт…",
        "login.success": "Вход выполнен. Открываем кабинет…",
        "login.failed": "Не удалось войти.",
        "login.note": "Сессия хранится в защищённой cookie браузера. Один идентификатор кабинета не даёт доступ.",
        "magic.eyebrow": "Одноразовый доступ",
        "magic.title": "Вход по magic link",
        "magic.lead": "Откройте полную ссылку или вставьте одноразовый token. Он истекает и не может быть использован повторно.",
        "magic.tenant": "Идентификатор кабинета",
        "magic.token": "Magic token",
        "magic.button": "Войти по token",
        "magic.required": "Magic token обязателен.",
        "magic.checking": "Проверяем token…",
        "magic.success": "Вход выполнен. Открываем кабинет…",
        "magic.failed": "Не удалось войти по magic link.",
        "magic.note": "Токены хранятся только в виде hash и после проверки создают ту же закрытую owner-сессию.",
        "logout.eyebrow": "Сессия завершена",
        "logout.title": "Вы вышли из аккаунта",
        "logout.text": "Owner- и admin-сессии браузера на этом устройстве очищены.",
        "logout.login": "Войти снова",
        "logout.home": "Вернуться на сайт",
        "legal.updated": "Информация для текущей контролируемой фазы сервиса",
        "privacy.title": "Уведомление о конфиденциальности",
        "privacy.lead": "Здесь описаны основные категории данных, которые Repliq обрабатывает при регистрации, работе владельца и клиентских диалогах.",
        "privacy.s1": "Какие данные обрабатываются",
        "privacy.s1_text": "Данные кабинета и владельца, настройки бизнеса, события авторизации и безопасности, содержание диалогов клиентов, данные записи и технические журналы, необходимые для работы и защиты сервиса.",
        "privacy.s2": "Зачем они используются",
        "privacy.s2_text": "Для создания и защиты кабинетов, работы рецепциониста и записи, подключения настроенных каналов и календарей, аналитики владельца, защиты от злоупотреблений и диагностики.",
        "privacy.s3": "Поставщики сервиса",
        "privacy.s3_text": "Сервис может использовать настроенных поставщиков хостинга, AI, сообщений, email и календаря. Конкретный состав зависит от deployment и пилотного соглашения.",
        "privacy.s4": "Cookies и хранение в браузере",
        "privacy.s4_text": "Repliq использует необходимые cookies для owner/admin-сессий, CSRF-защиты и выбранного языка интерфейса. Рекламные cookies в текущем продукте не используются.",
        "privacy.s5": "Хранение и доступ",
        "privacy.s5_text": "Сроки зависят от типа данных, настройки кабинета и операционных требований. Доступ ограничен tenant- и role-границами. Не следует вводить лишние чувствительные данные в знания бизнеса или тестовые диалоги.",
        "privacy.s6": "Запросы и контакт",
        "privacy.s6_text": "По вопросам доступа, исправления или удаления используйте настроенный контакт Repliq или канал, предоставленный при подключении. Может потребоваться проверка личности и доступа к кабинету.",
        "privacy.disclaimer": "Перед широким коммерческим запуском уведомление следует юридически проверить и дополнить данными оператора, контактом контролёра, сроками хранения и subprocessors финального deployment.",
        "terms.title": "Условия сервиса",
        "terms.lead": "Эти условия описывают текущий контролируемый сервис Repliq и не заменяют подписанное пилотное или коммерческое соглашение.",
        "terms.s1": "Объём сервиса",
        "terms.s1_text": "Repliq предоставляет настраиваемый кабинет владельца и AI-assisted процессы общения с клиентами. Каналы, календарь, billing и support зависят от конфигурации кабинета.",
        "terms.s2": "Обязанности владельца",
        "terms.s2_text": "Владелец отвечает за точные данные бизнеса, услуги, цены, правила, доступность, законность коммуникаций и надлежащую защиту owner-аккаунта.",
        "terms.s3": "AI и автоматизация",
        "terms.s3_text": "Автоматические ответы могут быть неточными. Бизнесу следует проверять настройки и важные сценарии в preview. Repliq не гарантирует понимание каждого сообщения или постоянную доступность внешних провайдеров.",
        "terms.s4": "Аккаунты и безопасность",
        "terms.s4_text": "Коды, magic links и сессии должны храниться в тайне. Доступ может быть ограничен для защиты сервиса, расследования злоупотреблений или выполнения требований закона.",
        "terms.s5": "Тарифы и оплата",
        "terms.s5_text": "Текущий продукт поддерживает controlled subscription status и основу ручного billing. Цена, trial и оплата определяются в предложении или соглашении; сайт не обещает автоматический checkout.",
        "terms.s6": "Доступность и изменения",
        "terms.s6_text": "Функции могут меняться в контролируемой фазе. Существенные операционные изменения должны сообщаться через согласованный owner- или support-канал.",
        "terms.s7": "Ограничение",
        "terms.s7_text": "Сервис не заменяет профессиональную медицинскую, юридическую, финансовую или экстренную помощь. Бизнес отвечает за решения для клиентов и проверку ситуаций с высоким риском.",
        "terms.disclaimer": "Перед широкими продажами условия требуют юридической проверки и дополнения данными оператора, применимым правом, лимитами ответственности, отменой и коммерческими условиями.",
        "contact.title": "Связаться с Repliq",
        "contact.lead": "Выберите подходящий путь. Публичные контактные данные можно настроить для коммерческого deployment, не раскрывая частные admin-каналы.",
        "contact.new_title": "Новый кабинет",
        "contact.new_text": "Создайте контролируемый кабинет и пройдите guided setup владельца.",
        "contact.owner_title": "Действующий владелец",
        "contact.owner_text": "Войдите, чтобы проверить настройку, аккаунт и доступный контекст поддержки конкретного кабинета.",
        "contact.direct_title": "Прямой контакт",
        "contact.direct_text": "Публичный контактный email для этого deployment не настроен. Контакты пилота предоставляются при подключении.",
        "contact.email_label": "Написать нам",
        "support.title": "Поддержка Repliq",
        "support.lead": "Начните с owner workspace, чтобы запрос был связан с правильным tenant и его настройками.",
        "support.s1": "Не получается войти",
        "support.s1_text": "Проверьте идентификатор кабинета и email владельца. Используйте резервный код или действующий одноразовый magic link. Не публикуйте credentials в чатах.",
        "support.s2": "Проблема настройки или канала",
        "support.s2_text": "Откройте Setup Health, Calendar или Telegram и сохраните видимый статус, не передавая токены и raw secrets.",
        "support.s3": "Неожиданный ответ клиенту",
        "support.s3_text": "Запишите tenant, канал, примерное время и формулировку клиента. Не включайте лишние персональные данные.",
        "support.s4": "Проблема записи или календаря",
        "support.s4_text": "Проверьте выбранный календарь, доступность и длительность услуги. Сначала используйте preview: live-тест может создать или изменить событие.",
        "support.cta": "Открыть вход владельца",
        "common.back_home": "На главную",
        "common.open_signup": "Создать кабинет",
        "common.open_login": "Вход владельца",
        "common.yes": "Да",
        "common.no": "Нет",
        "common.loading": "Загрузка…",
    },
    "lv": {
        "meta.home": "Repliq — AI administrators mazajiem un vidējiem uzņēmumiem",
        "meta.home_desc": "Repliq palīdz uzņēmumiem atbildēt uz klientu ziņām, izskaidrot pakalpojumus un atbalstīt pierakstu vienotā īpašnieka darba vidē.",
        "meta.signup": "Izveidot Repliq darba vidi",
        "meta.login": "Īpašnieka pieslēgšanās — Repliq",
        "meta.magic": "Pieslēgšanās ar maģisko saiti — Repliq",
        "meta.privacy": "Privātums — Repliq",
        "meta.terms": "Noteikumi — Repliq",
        "meta.contact": "Kontakti — Repliq",
        "meta.support": "Atbalsts — Repliq",
        "brand.tagline": "AI administrators ikdienas saziņai ar klientiem",
        "nav.product": "Produkts",
        "nav.how": "Kā tas darbojas",
        "nav.security": "Drošība",
        "nav.support": "Atbalsts",
        "nav.login": "Īpašnieka pieslēgšanās",
        "nav.signup": "Izveidot darba vidi",
        "nav.open": "Atvērt izvēlni",
        "nav.language": "Valoda",
        "footer.product": "Produkts",
        "footer.company": "Informācija",
        "footer.account": "Konts",
        "footer.home": "Sākums",
        "footer.signup": "Izveidot darba vidi",
        "footer.login": "Īpašnieka pieslēgšanās",
        "footer.privacy": "Privātums",
        "footer.terms": "Noteikumi",
        "footer.contact": "Kontakti",
        "footer.support": "Atbalsts",
        "footer.note": "Repliq pašlaik tiek piedāvāts kā kontrolēts SMB pakalpojums. Funkciju un integrāciju pieejamība ir atkarīga no darba vides konfigurācijas.",
        "home.eyebrow": "Sakārtota klientu saziņa",
        "home.title": "Praktisks AI administrators ziņām, BUJ un pierakstam.",
        "home.lead": "Repliq palīdz uzņēmumam sniegt konsekventas atbildes, izskaidrot pakalpojumus un virzīt klientu uz pierakstu, saglabājot īpašnieka kontroli.",
        "home.cta": "Izveidot darba vidi",
        "home.login": "Atvērt īpašnieka kontu",
        "home.scope": "Teksta SMB produkts",
        "home.scope_note": "Paredzēts kontrolētai ieviešanai un reālai uzņēmuma konfigurācijai — bez solījuma, ka katrs kanāls vai maksājums jau ir pilnībā automatizēts.",
        "home.problem_kicker": "Ikdienas problēma",
        "home.problem_title": "Klientu jautājumi pienāk, kamēr komanda ir aizņemta.",
        "home.problem_text": "Cenas, darba laiks, pieejamība un pieraksta maiņa atkārtojas katru dienu. Repliq sasaista atbildes ar uzņēmuma iestatījumiem, nevis izkaisītām piezīmēm.",
        "home.feature1_title": "Atbildes uz biežiem jautājumiem",
        "home.feature1_text": "Izmantojiet pakalpojumu katalogu un uzņēmuma zināšanas, lai atbildētu uz biežiem klientu jautājumiem atbalstītajās valodās.",
        "home.feature2_title": "Pieraksta procesu atbalsts",
        "home.feature2_text": "Vadiet pierakstu, pārcelšanu un atcelšanu esošajā kontrolētajā kalendāra procesā.",
        "home.feature3_title": "Īpašnieka pārskatāmība",
        "home.feature3_text": "Pārbaudiet iestatījumu kvalitāti, sarunu analītiku, atkārtotas saziņas kandidātus un gatavību palaišanai.",
        "home.how_kicker": "Kā tas darbojas",
        "home.how_title": "No uzņēmuma iestatīšanas līdz klientu sarunām.",
        "home.step1": "Izveidojiet darba vidi",
        "home.step1_text": "Norādiet uzņēmuma nosaukumu, īpašnieka e-pastu, darba laiku, laika joslu un galveno klientu valodu.",
        "home.step2": "Konfigurējiet uzņēmumu",
        "home.step2_text": "Pievienojiet pakalpojumus, cenas, BUJ, noteikumus, kalendāra pieejamību un pilotam izmantoto kanālu.",
        "home.step3": "Pārbaudiet un palaidiet",
        "home.step3_text": "Testējiet atbildes drošā priekšskatījumā, pārbaudiet gatavību un ieslēdziet saskaņoto klientu plūsmu.",
        "home.control_kicker": "Īpašnieka kontrole",
        "home.control_title": "AI vada sarunu. Noteikumus nosaka uzņēmums.",
        "home.control_text": "Repliq izmanto konfigurēto katalogu, uzņēmuma zināšanas un pieejamību. Darba vide rāda iestatījumu un sarunu pārskatāmību, neatklājot iekšējos noslēpumus klienta kontam.",
        "home.control1": "Atdalīta īpašnieka un administratora piekļuve",
        "home.control2": "Drošs priekšskatījums bez kalendāra ierakstiem un ārējiem ziņojumiem",
        "home.control3": "Tikai lasāma analītika un follow-up pārskatāmība",
        "home.control4": "Īpašnieka saskarne LV, RU un EN",
        "home.safety_kicker": "Drošība pēc uzbūves",
        "home.safety_title": "Kontrolētas darbības neierobežota čatbota vietā.",
        "home.safety_text": "Valodas modelis palīdz saprast klienta nolūku. Pieraksts un citas darbības paliek lietotnes workflow ar tenant robežām, piekļuves kontroli un gatavības pārbaudēm.",
        "home.audience_kicker": "Pakalpojumu uzņēmumiem",
        "home.audience_title": "Elastīgs pamats klīnikām, saloniem un citām komandām, kas strādā pēc pieraksta.",
        "home.audience_text": "Darba vide atbalsta konfigurējamus pakalpojumus, zināšanas, darba laiku, valodu un kanālus. Katra palaišana balstās faktiskajā tenant konfigurācijā.",
        "home.final_title": "Sāciet ar kontrolētu darba vidi.",
        "home.final_text": "Izveidojiet īpašnieka kontu, pabeidziet iestatīšanas sarakstu un pārbaudiet klienta pieredzi pirms palaišanas.",
        "signup.eyebrow": "Darba vides izveide",
        "signup.title": "Izveidojiet savu Repliq darba vidi",
        "signup.lead": "Sāciet ar būtiskāko uzņēmuma informāciju. Pakalpojumus, BUJ, kalendāru un kanālu varēsiet pabeigt pēc reģistrācijas.",
        "signup.business": "Uzņēmuma nosaukums",
        "signup.slug": "Darba vides identifikators",
        "signup.slug_help": "Īss tehnisks identifikators. Tas tiek ieteikts no uzņēmuma nosaukuma un pirms izveides ir maināms.",
        "signup.email": "Īpašnieka e-pasts",
        "signup.phone": "Uzņēmuma tālrunis",
        "signup.type": "Uzņēmuma veids",
        "signup.language": "Galvenā klientu valoda",
        "signup.language_help": "Tā nosaka sākotnējo uzņēmuma valodu, nevis šīs vietnes valodu.",
        "signup.timezone": "Laika josla",
        "signup.hours": "Darba laiks",
        "signup.start": "Sākums",
        "signup.end": "Beigas",
        "signup.terms_prefix": "Apstiprinu, ka tas ir reāls uzņēmuma pieprasījums, un piekrītu",
        "signup.terms_link": "Noteikumiem",
        "signup.privacy_link": "Privātuma paziņojumam",
        "signup.button": "Izveidot darba vidi",
        "signup.creating": "Veidojam darba vidi…",
        "signup.required": "Uzņēmuma nosaukums un īpašnieka e-pasts ir obligāti.",
        "signup.confirm": "Lūdzu, piekrītiet Noteikumiem un Privātuma paziņojumam.",
        "signup.failed": "Darba vidi neizdevās izveidot.",
        "signup.success": "Darba vide izveidota. Īpašnieka sesija ir aktīva.",
        "signup.result_title": "Darba vide ir gatava",
        "signup.result_tenant": "Darba vide",
        "signup.result_owner": "Īpašnieks",
        "signup.result_session": "Īpašnieka sesija izveidota",
        "signup.result_next": "Turpiniet privātajā iestatīšanas sarakstā un pabeidziet uzņēmuma konfigurāciju.",
        "signup.continue": "Turpināt iestatīšanu",
        "signup.copy": "Kopēt rezerves pieslēgšanās kodu",
        "signup.code_note": "Glabājiet rezerves kodu droši. Tas tiek parādīts vienu reizi. Nesūtiet kodus vai maģiskās saites atbalsta čatos.",
        "signup.details": "Reģistrācijas tehniskā informācija",
        "signup.readiness": "Kontrolēta publiskā reģistrācija ir pieejama",
        "login.eyebrow": "Īpašnieka konts",
        "login.title": "Pieslēdzieties darba videi",
        "login.lead": "Izmantojiet darba vides identifikatoru, īpašnieka e-pastu un rezerves pieslēgšanās kodu.",
        "login.tenant": "Darba vides identifikators",
        "login.email": "Īpašnieka e-pasts",
        "login.code": "Pieslēgšanās kods",
        "login.button": "Pieslēgties",
        "login.magic": "Izmantot maģisko tokenu",
        "login.required": "Īpašnieka e-pasts un pieslēgšanās kods ir obligāti.",
        "login.checking": "Pārbaudām kontu…",
        "login.success": "Pieslēgšanās veiksmīga. Atveram darba vidi…",
        "login.failed": "Pieslēgšanās neizdevās.",
        "login.note": "Sesija tiek glabāta drošā pārlūka cookie. Darba vides identifikators viens pats nepiešķir piekļuvi.",
        "magic.eyebrow": "Vienreizēja piekļuve",
        "magic.title": "Pieslēgšanās ar maģisko saiti",
        "magic.lead": "Atveriet pilno saiti vai ievadiet vienreizējo tokenu. Tam ir termiņš, un to nevar izmantot atkārtoti.",
        "magic.tenant": "Darba vides identifikators",
        "magic.token": "Maģiskais tokens",
        "magic.button": "Pieslēgties ar tokenu",
        "magic.required": "Maģiskais tokens ir obligāts.",
        "magic.checking": "Pārbaudām tokenu…",
        "magic.success": "Pieslēgšanās veiksmīga. Atveram darba vidi…",
        "magic.failed": "Pieslēgšanās ar maģisko saiti neizdevās.",
        "magic.note": "Tokeni tiek glabāti tikai hash veidā un pēc pārbaudes izveido to pašu privāto īpašnieka sesiju.",
        "logout.eyebrow": "Sesija aizvērta",
        "logout.title": "Jūs esat izrakstījies",
        "logout.text": "Šajā ierīcē tika notīrītas īpašnieka un administratora pārlūka sesijas.",
        "logout.login": "Pieslēgties vēlreiz",
        "logout.home": "Atgriezties vietnē",
        "legal.updated": "Informācija pašreizējam kontrolētā pakalpojuma posmam",
        "privacy.title": "Privātuma paziņojums",
        "privacy.lead": "Šeit aprakstītas galvenās informācijas kategorijas, ko Repliq apstrādā reģistrācijas, īpašnieka darba un klientu sarunu laikā.",
        "privacy.s1": "Kādu informāciju apstrādājam",
        "privacy.s1_text": "Darba vides un īpašnieka datus, uzņēmuma konfigurāciju, autentifikācijas un drošības notikumus, klientu sarunu saturu, pieraksta datus un tehniskos žurnālus pakalpojuma darbībai un aizsardzībai.",
        "privacy.s2": "Kāpēc tā tiek izmantota",
        "privacy.s2_text": "Lai izveidotu un aizsargātu darba vides, nodrošinātu administratora un pieraksta funkcijas, savienotu konfigurētos kanālus un kalendārus, rādītu analītiku, novērstu ļaunprātīgu izmantošanu un diagnosticētu problēmas.",
        "privacy.s3": "Pakalpojumu sniedzēji",
        "privacy.s3_text": "Pakalpojums var izmantot konfigurētus hostinga, AI, ziņojumu, e-pasta un kalendāra sniedzējus. Precīzs sastāvs ir atkarīgs no deployment un pilota vienošanās.",
        "privacy.s4": "Cookies un pārlūka glabātuve",
        "privacy.s4_text": "Repliq izmanto nepieciešamās cookies īpašnieka un administratora sesijām, CSRF aizsardzībai un izvēlētajai saskarnes valodai. Pašreizējā produktā reklāmas cookies netiek izmantotas.",
        "privacy.s5": "Glabāšana un piekļuve",
        "privacy.s5_text": "Glabāšanas termiņi ir atkarīgi no datu veida, darba vides konfigurācijas un darbības prasībām. Piekļuve ir ierobežota ar tenant un lomu robežām. Neievadiet nevajadzīgus sensitīvus datus uzņēmuma zināšanās vai testa sarunās.",
        "privacy.s6": "Pieprasījumi un kontakti",
        "privacy.s6_text": "Piekļuves, labošanas vai dzēšanas jautājumiem izmantojiet konfigurēto Repliq atbalsta kontaktu vai kanālu, kas sniegts ieviešanas laikā. Var būt nepieciešama identitātes un darba vides piekļuves pārbaude.",
        "privacy.disclaimer": "Pirms plašas komerciālas palaišanas paziņojums juridiski jāpārskata un jāpapildina ar operatora datiem, pārziņa kontaktu, glabāšanas termiņiem un gala deployment apakšapstrādātājiem.",
        "terms.title": "Pakalpojuma noteikumi",
        "terms.lead": "Šie noteikumi apraksta pašreizējo kontrolēto Repliq pakalpojumu un neaizstāj parakstītu pilota vai komerclīgumu.",
        "terms.s1": "Pakalpojuma apjoms",
        "terms.s1_text": "Repliq nodrošina konfigurējamu īpašnieka darba vidi un AI atbalstītas klientu saziņas plūsmas. Kanāli, kalendārs, norēķini un atbalsts ir atkarīgi no konfigurācijas.",
        "terms.s2": "Īpašnieka pienākumi",
        "terms.s2_text": "Īpašnieks atbild par precīzu uzņēmuma informāciju, pakalpojumiem, cenām, noteikumiem, pieejamību, likumīgu saziņu un pienācīgu konta aizsardzību.",
        "terms.s3": "AI un automatizācija",
        "terms.s3_text": "Automātiskas atbildes var būt neprecīzas. Uzņēmumam jāpārbauda konfigurācija un svarīgas plūsmas priekšskatījumā. Repliq negarantē katras ziņas izpratni vai ārējo sniedzēju nepārtrauktu pieejamību.",
        "terms.s4": "Konti un drošība",
        "terms.s4_text": "Pieslēgšanās kodi, maģiskās saites un sesijas jāglabā privāti. Piekļuve var tikt ierobežota pakalpojuma aizsardzībai, ļaunprātīgas izmantošanas izmeklēšanai vai juridisku pienākumu izpildei.",
        "terms.s5": "Plāni un maksājumi",
        "terms.s5_text": "Pašreizējais produkts atbalsta kontrolētu abonementa statusu un manuālu norēķinu pamatu. Cena, izmēģinājums un maksājumi tiek noteikti piedāvājumā vai līgumā; vietne nesola automātisku checkout.",
        "terms.s6": "Pieejamība un izmaiņas",
        "terms.s6_text": "Kontrolētajā posmā funkcijas var mainīties. Būtiskas darbības izmaiņas jāpaziņo caur saskaņoto īpašnieka vai atbalsta kanālu.",
        "terms.s7": "Ierobežojums",
        "terms.s7_text": "Pakalpojums neaizstāj profesionālu medicīnisku, juridisku, finanšu vai neatliekamu palīdzību. Uzņēmums atbild par klientu lēmumiem un augsta riska situāciju pārbaudi.",
        "terms.disclaimer": "Pirms plašas pārdošanas noteikumiem nepieciešama juridiska pārbaude un papildinājums ar operatoru, piemērojamo likumu, atbildības limitiem, atcelšanu un komerciālajiem noteikumiem.",
        "contact.title": "Sazinieties ar Repliq",
        "contact.lead": "Izvēlieties situācijai atbilstošo ceļu. Publisko kontaktinformāciju var konfigurēt gala komerciālajam deployment, neatklājot privātus administratora kanālus.",
        "contact.new_title": "Jauna darba vide",
        "contact.new_text": "Izveidojiet kontrolētu darba vidi un turpiniet vadīto īpašnieka iestatīšanu.",
        "contact.owner_title": "Esošs īpašnieks",
        "contact.owner_text": "Pieslēdzieties, lai pārskatītu iestatījumus, kontu un konkrētajai darba videi pieejamo atbalsta kontekstu.",
        "contact.direct_title": "Tiešs kontakts",
        "contact.direct_text": "Šim deployment publisks kontakta e-pasts nav konfigurēts. Pilota kontaktinformācija tiek sniegta ieviešanas laikā.",
        "contact.email_label": "Rakstīt mums",
        "support.title": "Repliq atbalsts",
        "support.lead": "Sāciet ar īpašnieka darba vidi, lai pieprasījums būtu saistīts ar pareizo tenant un konfigurāciju.",
        "support.s1": "Nevar pieslēgties",
        "support.s1_text": "Pārbaudiet darba vides identifikatoru un īpašnieka e-pastu. Izmantojiet rezerves kodu vai derīgu vienreizēju maģisko saiti. Nepublicējiet credentials čatos.",
        "support.s2": "Iestatījumu vai kanāla problēma",
        "support.s2_text": "Atveriet Setup Health, Calendar vai Telegram un fiksējiet redzamo statusu, neatklājot tokenus vai raw secrets.",
        "support.s3": "Negaidīta atbilde klientam",
        "support.s3_text": "Pierakstiet tenant, kanālu, aptuveno laiku un klienta formulējumu. Ziņojumā neiekļaujiet nevajadzīgus personas datus.",
        "support.s4": "Pieraksta vai kalendāra problēma",
        "support.s4_text": "Pārbaudiet izvēlēto kalendāru, pieejamību un pakalpojuma ilgumu. Vispirms izmantojiet preview, jo live tests var izveidot vai mainīt notikumu.",
        "support.cta": "Atvērt īpašnieka pieslēgšanos",
        "common.back_home": "Atpakaļ uz sākumu",
        "common.open_signup": "Izveidot darba vidi",
        "common.open_login": "Īpašnieka pieslēgšanās",
        "common.yes": "Jā",
        "common.no": "Nē",
        "common.loading": "Ielādē…",
    },
}

_PUBLIC_TEXT["en"].update({
    "footer.magic": "Magic link",
    "home.preview_state": "Safe preview",
    "home.preview_setup": "Setup",
    "home.preview_channel": "Channel",
    "home.preview_preview": "Preview",
    "home.preview_ready": "Ready",
    "signup.type_clinic": "Clinic",
    "signup.type_barbershop": "Barbershop",
    "signup.type_salon": "Salon",
    "signup.type_dentistry": "Dentistry",
    "signup.type_auto_service": "Auto service",
    "signup.type_restaurant": "Restaurant",
    "signup.type_other": "Other",
})
_PUBLIC_TEXT["ru"].update({
    "footer.magic": "Вход по magic link",
    "home.preview_state": "Безопасный preview",
    "home.preview_setup": "Настройка",
    "home.preview_channel": "Канал",
    "home.preview_preview": "Предпросмотр",
    "home.preview_ready": "Готов",
    "signup.type_clinic": "Клиника",
    "signup.type_barbershop": "Барбершоп",
    "signup.type_salon": "Салон",
    "signup.type_dentistry": "Стоматология",
    "signup.type_auto_service": "Автосервис",
    "signup.type_restaurant": "Ресторан",
    "signup.type_other": "Другое",
})
_PUBLIC_TEXT["lv"].update({
    "footer.magic": "Pieslēgšanās ar maģisko saiti",
    "home.preview_state": "Drošs priekšskatījums",
    "home.preview_setup": "Iestatīšana",
    "home.preview_channel": "Kanāls",
    "home.preview_preview": "Priekšskatījums",
    "home.preview_ready": "Gatavs",
    "signup.type_clinic": "Klīnika",
    "signup.type_barbershop": "Frizētava",
    "signup.type_salon": "Salons",
    "signup.type_dentistry": "Zobārstniecība",
    "signup.type_auto_service": "Autoserviss",
    "signup.type_restaurant": "Restorāns",
    "signup.type_other": "Cits",
})

# Keep language catalogs aligned. English is the canonical fallback.
for _lang in ("lv", "ru"):
    for _key, _value in _PUBLIC_TEXT["en"].items():
        _PUBLIC_TEXT[_lang].setdefault(_key, _value)


PUBLIC_UI_CSS = r"""
:root{--p-ink:#111827;--p-muted:#667085;--p-border:#e4e7ec;--p-soft:#f7f8fa;--p-accent:#5b5cf0;--p-accent2:#8b5cf6;--p-green:#067647;--p-red:#b42318;--p-warn:#b54708;--p-shadow:0 18px 50px rgba(16,24,40,.08);--p-radius:24px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body.rp-body{margin:0;background:#fff;color:var(--p-ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}.rp-container{width:min(1160px,calc(100% - 40px));margin:0 auto}.rp-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.9);backdrop-filter:blur(18px);border-bottom:1px solid rgba(228,231,236,.82)}.rp-header-inner{height:76px;display:flex;align-items:center;justify-content:space-between;gap:24px}.rp-brand{display:inline-flex;align-items:center;gap:11px;color:var(--p-ink);text-decoration:none;min-width:0}.rp-mark{width:38px;height:38px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,var(--p-accent),var(--p-accent2));color:#fff;font-weight:900;box-shadow:0 10px 24px rgba(91,92,240,.25)}.rp-brand strong{font-size:18px;letter-spacing:-.03em}.rp-brand small{display:block;color:var(--p-muted);font-size:11px;white-space:nowrap}.rp-nav{display:flex;align-items:center;gap:24px}.rp-nav>a{color:#344054;text-decoration:none;font-size:14px;font-weight:700}.rp-nav>a:hover{color:var(--p-accent)}.rp-actions{display:flex;align-items:center;gap:10px}.rp-lang{display:flex;align-items:center;padding:3px;background:var(--p-soft);border:1px solid var(--p-border);border-radius:12px}.rp-lang a{display:inline-flex;align-items:center;justify-content:center;border:0;background:transparent;color:#667085;font-size:11px;font-weight:800;padding:7px 8px;border-radius:9px;cursor:pointer;text-decoration:none}.rp-lang a.active{background:#fff;color:var(--p-ink);box-shadow:0 2px 8px rgba(16,24,40,.08)}.rp-button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;border:1px solid transparent;border-radius:13px;padding:10px 16px;text-decoration:none;font:inherit;font-size:14px;font-weight:800;cursor:pointer;transition:.18s ease}.rp-button-primary{background:linear-gradient(135deg,var(--p-accent),var(--p-accent2));color:#fff;box-shadow:0 10px 24px rgba(91,92,240,.22)}.rp-button-primary:hover{transform:translateY(-1px);box-shadow:0 14px 30px rgba(91,92,240,.28)}.rp-button-secondary{background:#fff;color:var(--p-ink);border-color:var(--p-border)}.rp-button-secondary:hover{border-color:#b9bdfb;background:#fafaff}.rp-button-ghost{background:transparent;color:#344054}.rp-mobile-menu{display:none;position:relative}.rp-mobile-menu>summary{list-style:none;display:grid;place-items:center;border:1px solid var(--p-border);background:#fff;width:42px;height:42px;border-radius:12px;font-size:20px;cursor:pointer;user-select:none}.rp-mobile-menu>summary::-webkit-details-marker{display:none}.rp-mobile-nav{display:none}.rp-mobile-menu[open] .rp-mobile-nav{display:grid;gap:8px;position:absolute;right:0;top:calc(100% + 10px);width:min(320px,calc(100vw - 24px));padding:12px;background:#fff;border:1px solid var(--p-border);border-radius:16px;box-shadow:var(--p-shadow);z-index:80}.rp-mobile-nav a{padding:10px 12px;border-radius:10px;color:#344054;text-decoration:none;font-weight:700}.rp-mobile-nav a:hover{background:var(--p-soft)}
.rp-hero{position:relative;overflow:hidden;padding:92px 0 72px;background:radial-gradient(circle at 75% 10%,rgba(139,92,246,.18),transparent 31%),radial-gradient(circle at 15% 40%,rgba(91,92,240,.13),transparent 29%),linear-gradient(#fff,#fafaff)}.rp-hero-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(360px,.95fr);gap:58px;align-items:center}.rp-eyebrow{display:inline-flex;align-items:center;gap:8px;border:1px solid #dddffe;background:#f7f7ff;color:#4546b8;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:850;letter-spacing:.03em;text-transform:uppercase}.rp-hero h1{font-size:clamp(44px,6vw,72px);line-height:1.02;letter-spacing:-.065em;margin:20px 0;color:#101828;max-width:820px}.rp-lead{font-size:clamp(18px,2vw,21px);line-height:1.62;color:#475467;max-width:720px}.rp-hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}.rp-proof{margin-top:26px;color:#667085;font-size:13px}.rp-product-card{background:#101828;color:#fff;border-radius:30px;padding:24px;box-shadow:0 30px 80px rgba(16,24,40,.24);transform:rotate(1deg)}.rp-product-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.rp-dot-group{display:flex;gap:6px}.rp-dot{width:8px;height:8px;border-radius:50%;background:#667085}.rp-product-state{font-size:11px;font-weight:800;color:#a6f4c5;background:rgba(6,118,71,.25);padding:6px 9px;border-radius:999px}.rp-chat{display:grid;gap:12px}.rp-message{max-width:85%;padding:12px 14px;border-radius:16px;font-size:13px;line-height:1.45}.rp-message.customer{justify-self:start;background:#344054;color:#f2f4f7;border-bottom-left-radius:5px}.rp-message.ai{justify-self:end;background:#fff;color:#101828;border-bottom-right-radius:5px}.rp-dashboard-mini{margin-top:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.rp-mini{background:#1d2939;border:1px solid #344054;border-radius:14px;padding:12px}.rp-mini span{display:block;color:#98a2b3;font-size:10px}.rp-mini strong{display:block;margin-top:5px;font-size:17px}.rp-section{padding:82px 0}.rp-section-soft{background:var(--p-soft)}.rp-section-dark{background:#101828;color:#fff}.rp-section-heading{max-width:760px;margin-bottom:38px}.rp-kicker{color:var(--p-accent);font-weight:850;font-size:12px;letter-spacing:.08em;text-transform:uppercase}.rp-section h2{font-size:clamp(32px,4vw,48px);line-height:1.1;letter-spacing:-.045em;margin:10px 0 14px}.rp-section-heading p,.rp-section-copy{color:#667085;font-size:17px;line-height:1.7}.rp-section-dark .rp-section-heading p,.rp-section-dark .rp-section-copy{color:#d0d5dd}.rp-grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.rp-grid-2{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}.rp-card{border:1px solid var(--p-border);border-radius:22px;padding:24px;background:#fff;box-shadow:0 8px 30px rgba(16,24,40,.035)}.rp-card h3{font-size:19px;letter-spacing:-.025em;margin:14px 0 8px}.rp-card p{color:#667085;line-height:1.65;margin:0}.rp-icon{width:42px;height:42px;border-radius:13px;background:#f0f0ff;color:var(--p-accent);display:grid;place-items:center;font-weight:900}.rp-step{position:relative;padding-top:62px}.rp-step-number{position:absolute;top:0;left:0;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:#101828;color:#fff;font-weight:900}.rp-check-list{display:grid;gap:14px;margin-top:24px}.rp-check{display:flex;gap:12px;align-items:flex-start;color:#344054;line-height:1.5}.rp-section-dark .rp-check{color:#eaecf0}.rp-check i{font-style:normal;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;flex:none;background:#dcfae6;color:#067647;font-size:12px;font-weight:900}.rp-cta{border-radius:30px;padding:46px;background:linear-gradient(135deg,#4f50dd,#7f56d9);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:28px;box-shadow:0 24px 60px rgba(91,92,240,.25)}.rp-cta h2{margin:0 0 10px;font-size:38px}.rp-cta p{margin:0;color:#e9e9ff;line-height:1.6;max-width:680px}.rp-cta .rp-button-secondary{border-color:transparent;white-space:nowrap}
.rp-page-hero{padding:70px 0 38px;background:linear-gradient(180deg,#f8f8ff,#fff)}.rp-page-hero h1{font-size:clamp(38px,5vw,58px);letter-spacing:-.055em;margin:14px 0 12px}.rp-page-hero p{font-size:18px;line-height:1.65;color:#667085;max-width:760px}.rp-page{padding:34px 0 80px}.rp-auth-wrap{width:min(620px,100%);margin:0 auto}.rp-form-card{background:#fff;border:1px solid var(--p-border);border-radius:26px;padding:30px;box-shadow:var(--p-shadow)}.rp-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.rp-field{display:grid;gap:7px}.rp-field-full{grid-column:1/-1}.rp-label{font-size:13px;color:#344054;font-weight:800}.rp-help{font-size:12px;color:#667085;line-height:1.45}.rp-input,.rp-select{width:100%;border:1px solid #d0d5dd;border-radius:12px;padding:12px 13px;background:#fff;color:#101828;font:inherit;outline:none}.rp-input:focus,.rp-select:focus{border-color:#7f80f5;box-shadow:0 0 0 4px rgba(91,92,240,.11)}.rp-inline{display:grid;grid-template-columns:1fr 1fr;gap:10px}.rp-checkbox{display:flex;gap:10px;align-items:flex-start;color:#475467;font-size:13px;line-height:1.5}.rp-checkbox input{margin-top:3px}.rp-status{margin-top:14px;border-radius:12px;padding:11px 13px;font-size:13px;display:none}.rp-status.show{display:block}.rp-status.ok{background:#ecfdf3;color:#067647;border:1px solid #abefc6}.rp-status.err{background:#fef3f2;color:#b42318;border:1px solid #fecdca}.rp-result{margin-top:20px;border:1px solid #abefc6;background:#f6fef9;border-radius:18px;padding:20px}.rp-hidden{display:none!important}.rp-details{margin-top:18px;border-top:1px solid var(--p-border);padding-top:14px}.rp-details summary{cursor:pointer;color:#667085;font-size:13px;font-weight:700}.rp-code{white-space:pre-wrap;background:#101828;color:#eaecf0;border-radius:14px;padding:14px;max-height:320px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}.rp-security{display:flex;gap:9px;margin-top:18px;color:#667085;font-size:12px;line-height:1.5}.rp-security i{font-style:normal;color:#067647;font-weight:900}.rp-honeypot{position:absolute!important;left:-10000px!important;width:1px!important;height:1px!important;overflow:hidden!important}.rp-legal{max-width:860px}.rp-legal section{padding:24px 0;border-bottom:1px solid var(--p-border)}.rp-legal h2{font-size:23px;margin:0 0 9px;letter-spacing:-.025em}.rp-legal p{color:#475467;line-height:1.75;margin:0}.rp-legal-note{margin-top:28px;border:1px solid #fedf89;background:#fffaeb;color:#93370d;border-radius:16px;padding:16px;line-height:1.55}.rp-contact-card{display:flex;flex-direction:column;justify-content:space-between;min-height:220px}.rp-contact-card .rp-button{align-self:flex-start;margin-top:22px}.rp-footer{border-top:1px solid var(--p-border);padding:54px 0 28px;background:#fff}.rp-footer-grid{display:grid;grid-template-columns:1.6fr repeat(3,1fr);gap:38px}.rp-footer h4{margin:0 0 13px;font-size:13px}.rp-footer-links{display:grid;gap:10px}.rp-footer a{color:#667085;text-decoration:none;font-size:13px}.rp-footer a:hover{color:var(--p-accent)}.rp-footer-note{color:#98a2b3;font-size:12px;line-height:1.55;max-width:390px;margin-top:16px}.rp-footer-bottom{border-top:1px solid var(--p-border);margin-top:36px;padding-top:20px;color:#98a2b3;font-size:12px;display:flex;justify-content:space-between;gap:16px}.rp-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:960px){.rp-nav{display:none}.rp-mobile-menu{display:block}.rp-header .rp-button-primary,.rp-header .rp-button-ghost{display:none}.rp-hero{padding-top:66px}.rp-hero-grid{grid-template-columns:1fr;gap:38px}.rp-product-card{max-width:640px;transform:none}.rp-grid-3{grid-template-columns:1fr}.rp-grid-2{grid-template-columns:1fr}.rp-footer-grid{grid-template-columns:1fr 1fr}.rp-cta{align-items:flex-start;flex-direction:column}.rp-dashboard-mini{grid-template-columns:repeat(3,1fr)}}
@media(max-width:640px){.rp-container{width:min(100% - 24px,1160px)}.rp-header-inner{height:68px}.rp-brand small{display:none}.rp-actions{gap:6px}.rp-lang button{padding:6px}.rp-hero{padding:54px 0}.rp-hero h1{font-size:42px}.rp-product-card{padding:17px;border-radius:22px}.rp-dashboard-mini{grid-template-columns:1fr}.rp-section{padding:60px 0}.rp-form-card{padding:20px;border-radius:20px}.rp-form-grid{grid-template-columns:1fr}.rp-field-full{grid-column:auto}.rp-inline{grid-template-columns:1fr}.rp-page-hero{padding:48px 0 24px}.rp-footer-grid{grid-template-columns:1fr}.rp-footer-bottom{flex-direction:column}.rp-cta{padding:28px}.rp-cta h2{font-size:30px}}
"""

PUBLIC_UI_JS = r"""
(function(){
  const supported=['lv','ru','en'];
  function setLanguage(lang){
    if(!supported.includes(lang))return;
    const link=document.querySelector('[data-rp-lang-link="'+lang+'"]');
    if(link&&link.href){window.location.assign(link.href);return;}
    const url=new URL(window.location.href);url.searchParams.set('ui_lang',lang);window.location.assign(url.toString());
  }
  document.querySelectorAll('[data-rp-mobile-nav] a').forEach(link=>link.addEventListener('click',()=>{
    const menu=link.closest('details');if(menu)menu.removeAttribute('open');
  }));
  window.RepliqPublic={
    setLanguage,
    esc:function(v){return v===null||v===undefined?'':String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');},
    boolLabel:function(v,yes,no){return v?yes:no;}
  };
})();
"""


def public_text(lang: str, key: str, **values: Any) -> str:
    normalized = normalize_ui_language(lang)
    value = _PUBLIC_TEXT.get(normalized, {}).get(key) or _PUBLIC_TEXT["en"].get(key) or key
    if values:
        try:
            return value.format(**values)
        except Exception:
            return value
    return value


def public_strings(lang: str, keys: Iterable[str]) -> Dict[str, str]:
    return {key: public_text(lang, key) for key in keys}


def public_translation_counts() -> Dict[str, int]:
    return {lang: len(_PUBLIC_TEXT.get(lang, {})) for lang in UI_SUPPORTED_LANGUAGES}


def public_language_urls(request: Any = None) -> Dict[str, str]:
    path = "/"
    pairs = []
    if request is not None:
        try:
            path = str(request.url.path or "/")
        except Exception:
            path = "/"
        try:
            pairs = [(str(k), str(v)) for k, v in request.query_params.multi_items() if str(k) != "ui_lang"]
        except Exception:
            pairs = []
    urls: Dict[str, str] = {}
    for code in UI_SUPPORTED_LANGUAGES:
        query = urllib.parse.urlencode(pairs + [("ui_lang", code)], doseq=True)
        urls[code] = f"{path}?{query}" if query else path
    return urls


def _language_buttons(lang: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    urls = language_urls or {code: f"?ui_lang={code}" for code in UI_SUPPORTED_LANGUAGES}
    return "".join(
        f'<a class="{"active" if code == lang else ""}" href="{html.escape(str(urls.get(code) or f"?ui_lang={code}"), quote=True)}" data-rp-lang-link="{code}" aria-current="{"true" if code == lang else "false"}" aria-label="{html.escape(public_text(lang, "nav.language"))}: {code.upper()}">{code.upper()}</a>'
        for code in UI_SUPPORTED_LANGUAGES
    )


def render_public_shell(
    *,
    title: str,
    description: str,
    lang: str,
    content_html: str,
    active: str = "",
    inline_script: str = "",
    extra_head: str = "",
    body_class: str = "",
    language_urls: Optional[Dict[str, str]] = None,
) -> str:
    normalized = normalize_ui_language(lang)
    def nav_class(key: str) -> str:
        return ' aria-current="page"' if active == key else ""
    lang_buttons = _language_buttons(normalized, language_urls)
    header = f'''<header class="rp-header"><div class="rp-container rp-header-inner">
<a class="rp-brand" href="/?ui_lang={normalized}"><span class="rp-mark">R</span><span><strong>Repliq</strong><small>{html.escape(public_text(normalized,"brand.tagline"))}</small></span></a>
<nav class="rp-nav" aria-label="Primary"><a href="/#product"{nav_class("product")}>{html.escape(public_text(normalized,"nav.product"))}</a><a href="/#how"{nav_class("how")}>{html.escape(public_text(normalized,"nav.how"))}</a><a href="/#security"{nav_class("security")}>{html.escape(public_text(normalized,"nav.security"))}</a><a href="/support?ui_lang={normalized}"{nav_class("support")}>{html.escape(public_text(normalized,"nav.support"))}</a></nav>
<div class="rp-actions"><div class="rp-lang" aria-label="{html.escape(public_text(normalized,"nav.language"))}">{lang_buttons}</div><a class="rp-button rp-button-ghost" href="/owner/login?ui_lang={normalized}">{html.escape(public_text(normalized,"nav.login"))}</a><a class="rp-button rp-button-primary" href="/public/signup?ui_lang={normalized}">{html.escape(public_text(normalized,"nav.signup"))}</a><details class="rp-mobile-menu"><summary aria-label="{html.escape(public_text(normalized,"nav.open"))}">☰</summary><nav class="rp-mobile-nav" data-rp-mobile-nav><a href="/#product">{html.escape(public_text(normalized,"nav.product"))}</a><a href="/#how">{html.escape(public_text(normalized,"nav.how"))}</a><a href="/#security">{html.escape(public_text(normalized,"nav.security"))}</a><a href="/support?ui_lang={normalized}">{html.escape(public_text(normalized,"nav.support"))}</a><a href="/owner/login?ui_lang={normalized}">{html.escape(public_text(normalized,"nav.login"))}</a><a href="/public/signup?ui_lang={normalized}">{html.escape(public_text(normalized,"nav.signup"))}</a></nav></details></div></div></header>'''
    footer = f'''<footer class="rp-footer"><div class="rp-container"><div class="rp-footer-grid"><div><a class="rp-brand" href="/?ui_lang={normalized}"><span class="rp-mark">R</span><span><strong>Repliq</strong><small>{html.escape(public_text(normalized,"brand.tagline"))}</small></span></a><p class="rp-footer-note">{html.escape(public_text(normalized,"footer.note"))}</p></div><div><h4>{html.escape(public_text(normalized,"footer.product"))}</h4><div class="rp-footer-links"><a href="/?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.home"))}</a><a href="/public/signup?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.signup"))}</a><a href="/support?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.support"))}</a></div></div><div><h4>{html.escape(public_text(normalized,"footer.company"))}</h4><div class="rp-footer-links"><a href="/privacy?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.privacy"))}</a><a href="/terms?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.terms"))}</a><a href="/contact?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.contact"))}</a></div></div><div><h4>{html.escape(public_text(normalized,"footer.account"))}</h4><div class="rp-footer-links"><a href="/owner/login?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.login"))}</a><a href="/owner/magic-login?ui_lang={normalized}">{html.escape(public_text(normalized,"footer.magic"))}</a></div></div></div><div class="rp-footer-bottom"><span>© Repliq</span><span>{html.escape(public_text(normalized,"legal.updated"))} · {CX3_PUBLIC_UI_VERSION}</span></div></div></footer>'''
    scripts = f'<script src="/assets/repliq-public.js?v={CX3_PUBLIC_UI_VERSION}"></script>'
    if inline_script:
        scripts += f"<script>{inline_script}</script>"
    return f'''<!doctype html><html lang="{normalized}"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><meta name="color-scheme" content="light"/><meta name="description" content="{html.escape(description, quote=True)}"/><meta name="robots" content="index,follow"/><meta property="og:type" content="website"/><meta property="og:title" content="{html.escape(title, quote=True)}"/><meta property="og:description" content="{html.escape(description, quote=True)}"/><title>{html.escape(title)}</title><link rel="icon" href="/favicon.svg" type="image/svg+xml"/><link rel="stylesheet" href="/assets/repliq-public.css?v={CX3_PUBLIC_UI_VERSION}"/>{extra_head}</head><body class="rp-body {html.escape(body_class, quote=True)}" data-rp-lang="{normalized}" data-rp-version="{CX3_PUBLIC_UI_VERSION}">{header}<main>{content_html}</main>{footer}{scripts}</body></html>'''


def public_response_headers(lang: str) -> Dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Content-Language": normalize_ui_language(lang),
        "X-Repliq-Public-UI": CX3_PUBLIC_UI_VERSION,
        "X-Repliq-UI": UI_FOUNDATION_VERSION,
    }


def resolve_public_language(request: Any = None) -> str:
    return resolve_ui_language(request)


def safe_public_email(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > 254 or "@" not in candidate or any(ch in candidate for ch in "\r\n<>"):
        return ""
    return candidate


def _esc_text(lang: str, key: str) -> str:
    return html.escape(public_text(lang, key))


def render_home_page(lang: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    content = f'''
<section class="rp-hero"><div class="rp-container rp-hero-grid"><div><span class="rp-eyebrow">{_esc_text(l,"home.eyebrow")}</span><h1>{_esc_text(l,"home.title")}</h1><p class="rp-lead">{_esc_text(l,"home.lead")}</p><div class="rp-hero-actions"><a class="rp-button rp-button-primary" href="/public/signup?ui_lang={l}">{_esc_text(l,"home.cta")}</a><a class="rp-button rp-button-secondary" href="/owner/login?ui_lang={l}">{_esc_text(l,"home.login")}</a></div><p class="rp-proof"><strong>{_esc_text(l,"home.scope")}</strong> · {_esc_text(l,"home.scope_note")}</p></div><div class="rp-product-card" aria-label="Repliq product preview"><div class="rp-product-top"><div class="rp-dot-group"><span class="rp-dot"></span><span class="rp-dot"></span><span class="rp-dot"></span></div><span class="rp-product-state">{_esc_text(l,"home.preview_state")}</span></div><div class="rp-chat"><div class="rp-message customer">{html.escape({'lv':'Labdien! Cik maksā konsultācija un vai ir laiks rīt?','ru':'Здравствуйте! Сколько стоит консультация и есть ли время завтра?','en':'Hi! How much is a consultation and is there time tomorrow?'}[l])}</div><div class="rp-message ai">{html.escape({'lv':'Konsultācija maksā 45 €. Rīt varu piedāvāt 11:00 vai 15:30. Kurš laiks der?','ru':'Консультация стоит 45 €. Завтра могу предложить 11:00 или 15:30. Какое время подходит?','en':'A consultation is €45. Tomorrow I can offer 11:00 or 15:30. Which time works?'}[l])}</div></div><div class="rp-dashboard-mini"><div class="rp-mini"><span>{_esc_text(l,"home.preview_setup")}</span><strong>92%</strong></div><div class="rp-mini"><span>{_esc_text(l,"home.preview_channel")}</span><strong>{_esc_text(l,"home.preview_ready")}</strong></div><div class="rp-mini"><span>{_esc_text(l,"home.preview_preview")}</span><strong>{_esc_text(l,"home.preview_state")}</strong></div></div></div></div></section>
<section class="rp-section" id="product"><div class="rp-container"><div class="rp-section-heading"><span class="rp-kicker">{_esc_text(l,"home.problem_kicker")}</span><h2>{_esc_text(l,"home.problem_title")}</h2><p>{_esc_text(l,"home.problem_text")}</p></div><div class="rp-grid-3"><article class="rp-card"><div class="rp-icon">01</div><h3>{_esc_text(l,"home.feature1_title")}</h3><p>{_esc_text(l,"home.feature1_text")}</p></article><article class="rp-card"><div class="rp-icon">02</div><h3>{_esc_text(l,"home.feature2_title")}</h3><p>{_esc_text(l,"home.feature2_text")}</p></article><article class="rp-card"><div class="rp-icon">03</div><h3>{_esc_text(l,"home.feature3_title")}</h3><p>{_esc_text(l,"home.feature3_text")}</p></article></div></div></section>
<section class="rp-section rp-section-soft" id="how"><div class="rp-container"><div class="rp-section-heading"><span class="rp-kicker">{_esc_text(l,"home.how_kicker")}</span><h2>{_esc_text(l,"home.how_title")}</h2></div><div class="rp-grid-3"><article class="rp-card rp-step"><span class="rp-step-number">1</span><h3>{_esc_text(l,"home.step1")}</h3><p>{_esc_text(l,"home.step1_text")}</p></article><article class="rp-card rp-step"><span class="rp-step-number">2</span><h3>{_esc_text(l,"home.step2")}</h3><p>{_esc_text(l,"home.step2_text")}</p></article><article class="rp-card rp-step"><span class="rp-step-number">3</span><h3>{_esc_text(l,"home.step3")}</h3><p>{_esc_text(l,"home.step3_text")}</p></article></div></div></section>
<section class="rp-section"><div class="rp-container rp-grid-2"><div><span class="rp-kicker">{_esc_text(l,"home.control_kicker")}</span><h2>{_esc_text(l,"home.control_title")}</h2><p class="rp-section-copy">{_esc_text(l,"home.control_text")}</p></div><div class="rp-card"><div class="rp-check-list"><div class="rp-check"><i>✓</i><span>{_esc_text(l,"home.control1")}</span></div><div class="rp-check"><i>✓</i><span>{_esc_text(l,"home.control2")}</span></div><div class="rp-check"><i>✓</i><span>{_esc_text(l,"home.control3")}</span></div><div class="rp-check"><i>✓</i><span>{_esc_text(l,"home.control4")}</span></div></div></div></div></section>
<section class="rp-section rp-section-dark" id="security"><div class="rp-container rp-grid-2"><div><span class="rp-kicker">{_esc_text(l,"home.safety_kicker")}</span><h2>{_esc_text(l,"home.safety_title")}</h2><p class="rp-section-copy">{_esc_text(l,"home.safety_text")}</p></div><div><span class="rp-kicker">{_esc_text(l,"home.audience_kicker")}</span><h2 style="font-size:34px">{_esc_text(l,"home.audience_title")}</h2><p class="rp-section-copy">{_esc_text(l,"home.audience_text")}</p></div></div></section>
<section class="rp-section"><div class="rp-container"><div class="rp-cta"><div><h2>{_esc_text(l,"home.final_title")}</h2><p>{_esc_text(l,"home.final_text")}</p></div><a class="rp-button rp-button-secondary" href="/public/signup?ui_lang={l}">{_esc_text(l,"home.cta")}</a></div></div></section>'''
    return render_public_shell(title=public_text(l,"meta.home"), description=public_text(l,"meta.home_desc"), lang=l, content_html=content, active="product", language_urls=language_urls)


def render_signup_page(lang: str, readiness: Dict[str, Any], language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    copy_keys = ["signup.creating","signup.required","signup.confirm","signup.failed","signup.success","signup.result_tenant","signup.result_owner","signup.result_session","signup.result_next","common.yes","common.no"]
    copy_json = json.dumps(public_strings(l, copy_keys), ensure_ascii=False)
    readiness_json = json.dumps(readiness or {}, ensure_ascii=False)
    content = f'''<section class="rp-page-hero"><div class="rp-container"><span class="rp-eyebrow">{_esc_text(l,"signup.eyebrow")}</span><h1>{_esc_text(l,"signup.title")}</h1><p>{_esc_text(l,"signup.lead")}</p></div></section><section class="rp-page"><div class="rp-container"><div class="rp-form-card"><div class="rp-form-grid"><div class="rp-field"><label class="rp-label" for="business_name">{_esc_text(l,"signup.business")} *</label><input class="rp-input" id="business_name" autocomplete="organization"/></div><div class="rp-field"><label class="rp-label" for="tenant_slug">{_esc_text(l,"signup.slug")}</label><input class="rp-input" id="tenant_slug"/><span class="rp-help">{_esc_text(l,"signup.slug_help")}</span></div><div class="rp-field"><label class="rp-label" for="owner_email">{_esc_text(l,"signup.email")} *</label><input class="rp-input" id="owner_email" type="email" autocomplete="email"/></div><div class="rp-field"><label class="rp-label" for="phone_number">{_esc_text(l,"signup.phone")}</label><input class="rp-input" id="phone_number" type="tel" autocomplete="tel"/></div><div class="rp-field"><label class="rp-label" for="business_type">{_esc_text(l,"signup.type")}</label><select class="rp-select" id="business_type"><option value="clinic">{_esc_text(l,"signup.type_clinic")}</option><option value="barbershop">{_esc_text(l,"signup.type_barbershop")}</option><option value="salon">{_esc_text(l,"signup.type_salon")}</option><option value="dentistry">{_esc_text(l,"signup.type_dentistry")}</option><option value="auto_service">{_esc_text(l,"signup.type_auto_service")}</option><option value="restaurant">{_esc_text(l,"signup.type_restaurant")}</option><option value="other">{_esc_text(l,"signup.type_other")}</option></select></div><div class="rp-field"><label class="rp-label" for="language">{_esc_text(l,"signup.language")}</label><select class="rp-select" id="language"><option value="lv">Latviešu</option><option value="ru">Русский</option><option value="en">English</option></select><span class="rp-help">{_esc_text(l,"signup.language_help")}</span></div><div class="rp-field"><label class="rp-label" for="timezone">{_esc_text(l,"signup.timezone")}</label><input class="rp-input" id="timezone" value="Europe/Riga"/></div><div class="rp-field"><label class="rp-label">{_esc_text(l,"signup.hours")}</label><div class="rp-inline"><div><label class="rp-help" for="work_start">{_esc_text(l,"signup.start")}</label><input class="rp-input" id="work_start" value="09:00"/></div><div><label class="rp-help" for="work_end">{_esc_text(l,"signup.end")}</label><input class="rp-input" id="work_end" value="18:00"/></div></div></div></div><div class="rp-honeypot" aria-hidden="true"><label for="website">Website</label><input id="website" autocomplete="off" tabindex="-1"/></div><label class="rp-checkbox" style="margin-top:20px"><input id="accepted_terms" type="checkbox"/><span>{_esc_text(l,"signup.terms_prefix")} <a href="/terms?ui_lang={l}" target="_blank" rel="noopener">{_esc_text(l,"signup.terms_link")}</a> &amp; <a href="/privacy?ui_lang={l}" target="_blank" rel="noopener">{_esc_text(l,"signup.privacy_link")}</a>.</span></label><button id="signup_button" class="rp-button rp-button-primary" style="margin-top:20px" type="button">{_esc_text(l,"signup.button")}</button><div id="status" class="rp-status" role="status" aria-live="polite"></div><div id="result" class="rp-result rp-hidden"><h2 style="margin-top:0">{_esc_text(l,"signup.result_title")}</h2><div id="summary"></div><div class="rp-hero-actions"><button id="continue_button" class="rp-button rp-button-primary" type="button">{_esc_text(l,"signup.continue")}</button><button id="copy_button" class="rp-button rp-button-secondary" type="button">{_esc_text(l,"signup.copy")}</button></div><p class="rp-help">{_esc_text(l,"signup.code_note")}</p><details class="rp-details"><summary>{_esc_text(l,"signup.details")}</summary><pre class="rp-code" id="raw"></pre></details></div><div class="rp-security"><i>✓</i><span>{_esc_text(l,"signup.readiness")}</span></div></div></div></section>'''
    script = r'''const READINESS=__READINESS__;const COPY=__COPY__;let latest=null;const el=id=>document.getElementById(id);function slugify(v){return String(v||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9_-]+/g,'_').replace(/[_-]{2,}/g,'_').replace(/^[_-]+|[_-]+$/g,'').slice(0,48)}function suggest(){if(el('tenant_slug').dataset.touched==='1')return;el('tenant_slug').value=slugify(el('business_name').value)}el('business_name').addEventListener('input',suggest);el('tenant_slug').addEventListener('input',()=>el('tenant_slug').dataset.touched='1');function status(kind,text){const n=el('status');n.className='rp-status show '+kind;n.textContent=text}function payload(){return{business_name:el('business_name').value.trim(),tenant_slug:el('tenant_slug').value.trim()||null,owner_email:el('owner_email').value.trim(),phone_number:el('phone_number').value.trim()||null,business_type:el('business_type').value,language:el('language').value,timezone:el('timezone').value.trim()||'Europe/Riga',work_start:el('work_start').value.trim()||'09:00',work_end:el('work_end').value.trim()||'18:00',accepted_terms:el('accepted_terms').checked,website:el('website').value||''}}async function signup(){const p=payload();if(!p.business_name||!p.owner_email){status('err',COPY['signup.required']);return}if(!p.accepted_terms){status('err',COPY['signup.confirm']);return}el('signup_button').disabled=true;status('ok',COPY['signup.creating']);try{const r=await fetch('/public/signup',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(p)});const data=await r.json().catch(()=>({}));latest=data;if(!r.ok||!data.ok){status('err',data.error||data.detail||COPY['signup.failed']);return}status('ok',COPY['signup.success']);el('result').classList.remove('rp-hidden');el('summary').innerHTML='<p><strong>'+RepliqPublic.esc(COPY['signup.result_tenant'])+':</strong> '+RepliqPublic.esc(data.tenant_id||'—')+'<br/><strong>'+RepliqPublic.esc(COPY['signup.result_owner'])+':</strong> '+RepliqPublic.esc(data.owner_email||'—')+'<br/><strong>'+RepliqPublic.esc(COPY['signup.result_session'])+':</strong> '+RepliqPublic.esc(data.owner_session_created?COPY['common.yes']:COPY['common.no'])+'</p><p>'+RepliqPublic.esc(COPY['signup.result_next'])+'</p>';const safe=JSON.parse(JSON.stringify(data));['owner_login_code','owner_magic_link_token','owner_magic_link_url'].forEach(k=>{if(safe[k])safe[k]='[returned_once_hidden_in_public_ui]'});el('raw').textContent=JSON.stringify(safe,null,2)}catch(e){status('err',COPY['signup.failed'])}finally{el('signup_button').disabled=false}}function openOwner(){if(!latest||!latest.links)return;location.href=latest.links.owner_get_started||latest.links.owner_workspace||latest.links.owner_dashboard||'/owner/login'}async function copyCode(){if(!latest||!latest.owner_login_code)return;try{await navigator.clipboard.writeText(latest.owner_login_code)}catch(e){}}el('signup_button').addEventListener('click',signup);el('continue_button').addEventListener('click',openOwner);el('copy_button').addEventListener('click',copyCode);'''.replace('__READINESS__', readiness_json).replace('__COPY__', copy_json)
    return render_public_shell(title=public_text(l,"meta.signup"), description=public_text(l,"signup.lead"), lang=l, content_html=content, active="signup", inline_script=script, language_urls=language_urls)


def render_login_page(lang: str, tenant_id: str, next_path: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    copy_json = json.dumps(public_strings(l,["login.required","login.checking","login.success","login.failed"]),ensure_ascii=False)
    content = f'''<section class="rp-page-hero"><div class="rp-container rp-auth-wrap"><span class="rp-eyebrow">{_esc_text(l,"login.eyebrow")}</span><h1>{_esc_text(l,"login.title")}</h1><p>{_esc_text(l,"login.lead")}</p></div></section><section class="rp-page"><div class="rp-container rp-auth-wrap"><div class="rp-form-card"><div class="rp-field"><label class="rp-label" for="tenant_id">{_esc_text(l,"login.tenant")}</label><input class="rp-input" id="tenant_id" autocomplete="organization"/></div><div class="rp-field" style="margin-top:16px"><label class="rp-label" for="owner_email">{_esc_text(l,"login.email")}</label><input class="rp-input" id="owner_email" type="email" autocomplete="email"/></div><div class="rp-field" style="margin-top:16px"><label class="rp-label" for="login_code">{_esc_text(l,"login.code")}</label><input class="rp-input" id="login_code" type="password" autocomplete="one-time-code"/></div><button id="login_button" class="rp-button rp-button-primary" style="width:100%;margin-top:20px" type="button">{_esc_text(l,"login.button")}</button><div id="msg" class="rp-status" role="status" aria-live="polite"></div><div style="text-align:center;margin-top:14px"><a id="magic_link" class="rp-button rp-button-ghost" href="#">{_esc_text(l,"login.magic")}</a></div><div class="rp-security"><i>✓</i><span>{_esc_text(l,"login.note")}</span></div></div></div></section>'''
    script = r'''const DEFAULT_TENANT=__TENANT__;const NEXT_PATH=__NEXT__;const COPY=__COPY__;const el=id=>document.getElementById(id);el('tenant_id').value=DEFAULT_TENANT||'clinic_demo';el('magic_link').href='/owner/magic-login?tenant_id='+encodeURIComponent(DEFAULT_TENANT||'clinic_demo')+'&ui_lang='+encodeURIComponent(document.body.dataset.rpLang||'en');function msg(kind,text){const n=el('msg');n.className='rp-status show '+kind;n.textContent=text}async function login(){const tenant_id=el('tenant_id').value.trim()||DEFAULT_TENANT||'clinic_demo';const owner_email=el('owner_email').value.trim();const login_code=el('login_code').value||'';if(!owner_email||!login_code.trim()){msg('err',COPY['login.required']);return}el('login_button').disabled=true;msg('ok',COPY['login.checking']);try{const r=await fetch('/owner/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({tenant_id,owner_email,login_code,next:NEXT_PATH})});const data=await r.json().catch(()=>({}));if(!r.ok||!data.ok){msg('err',data.error||data.detail||COPY['login.failed']);return}msg('ok',COPY['login.success']);location.href=data.redirect_url||('/owner/dashboard/ui?tenant_id='+encodeURIComponent(tenant_id))}catch(e){msg('err',COPY['login.failed'])}finally{el('login_button').disabled=false}}el('login_button').addEventListener('click',login);document.addEventListener('keydown',e=>{if(e.key==='Enter')login()});'''.replace('__TENANT__',json.dumps(tenant_id,ensure_ascii=False)).replace('__NEXT__',json.dumps(next_path,ensure_ascii=False)).replace('__COPY__',copy_json)
    return render_public_shell(title=public_text(l,"meta.login"), description=public_text(l,"login.lead"), lang=l, content_html=content, active="login", inline_script=script, language_urls=language_urls)


def render_magic_login_page(lang: str, tenant_id: str, next_path: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    copy_json = json.dumps(public_strings(l,["magic.required","magic.checking","magic.success","magic.failed"]),ensure_ascii=False)
    content = f'''<section class="rp-page-hero"><div class="rp-container rp-auth-wrap"><span class="rp-eyebrow">{_esc_text(l,"magic.eyebrow")}</span><h1>{_esc_text(l,"magic.title")}</h1><p>{_esc_text(l,"magic.lead")}</p></div></section><section class="rp-page"><div class="rp-container rp-auth-wrap"><div class="rp-form-card"><div class="rp-field"><label class="rp-label" for="tenant_id">{_esc_text(l,"magic.tenant")}</label><input class="rp-input" id="tenant_id" autocomplete="organization"/></div><div class="rp-field" style="margin-top:16px"><label class="rp-label" for="token">{_esc_text(l,"magic.token")}</label><input class="rp-input" id="token" type="password" autocomplete="one-time-code"/></div><button id="magic_button" class="rp-button rp-button-primary" style="width:100%;margin-top:20px" type="button">{_esc_text(l,"magic.button")}</button><div id="msg" class="rp-status" role="status" aria-live="polite"></div><div class="rp-security"><i>✓</i><span>{_esc_text(l,"magic.note")}</span></div></div></div></section>'''
    script = r'''const DEFAULT_TENANT=__TENANT__;const NEXT_PATH=__NEXT__;const COPY=__COPY__;const el=id=>document.getElementById(id);el('tenant_id').value=DEFAULT_TENANT||'clinic_demo';function msg(kind,text){const n=el('msg');n.className='rp-status show '+kind;n.textContent=text}async function login(){const tenant_id=el('tenant_id').value.trim()||DEFAULT_TENANT||'clinic_demo';const token=el('token').value||'';if(!token.trim()){msg('err',COPY['magic.required']);return}el('magic_button').disabled=true;msg('ok',COPY['magic.checking']);try{const r=await fetch('/owner/magic-login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({tenant_id,token,next:NEXT_PATH})});const data=await r.json().catch(()=>({}));if(!r.ok||!data.ok){msg('err',data.error||data.detail||COPY['magic.failed']);return}msg('ok',COPY['magic.success']);location.href=data.redirect_url||('/owner/dashboard/ui?tenant_id='+encodeURIComponent(data.tenant_id||tenant_id))}catch(e){msg('err',COPY['magic.failed'])}finally{el('magic_button').disabled=false}}el('magic_button').addEventListener('click',login);document.addEventListener('keydown',e=>{if(e.key==='Enter')login()});'''.replace('__TENANT__',json.dumps(tenant_id,ensure_ascii=False)).replace('__NEXT__',json.dumps(next_path,ensure_ascii=False)).replace('__COPY__',copy_json)
    return render_public_shell(title=public_text(l,"meta.magic"), description=public_text(l,"magic.lead"), lang=l, content_html=content, active="login", inline_script=script, language_urls=language_urls)


def render_logout_page(lang: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    content = f'''<section class="rp-page-hero"><div class="rp-container rp-auth-wrap"><span class="rp-eyebrow">{_esc_text(l,"logout.eyebrow")}</span><h1>{_esc_text(l,"logout.title")}</h1><p>{_esc_text(l,"logout.text")}</p></div></section><section class="rp-page"><div class="rp-container rp-auth-wrap"><div class="rp-form-card"><div class="rp-hero-actions" style="margin-top:0"><a class="rp-button rp-button-primary" href="/owner/login?ui_lang={l}">{_esc_text(l,"logout.login")}</a><a class="rp-button rp-button-secondary" href="/?ui_lang={l}">{_esc_text(l,"logout.home")}</a></div></div></div></section>'''
    return render_public_shell(title=public_text(l,"logout.title"), description=public_text(l,"logout.text"), lang=l, content_html=content, active="login", language_urls=language_urls)


def render_legal_page(lang: str, kind: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l = normalize_ui_language(lang)
    if kind == "privacy":
        prefix="privacy"; sections=range(1,7); title_key="meta.privacy"
    else:
        prefix="terms"; sections=range(1,8); title_key="meta.terms"
    parts="".join(f'<section><h2>{_esc_text(l,f"{prefix}.s{i}")}</h2><p>{_esc_text(l,f"{prefix}.s{i}_text")}</p></section>' for i in sections)
    content=f'''<section class="rp-page-hero"><div class="rp-container"><span class="rp-eyebrow">{_esc_text(l,"legal.updated")}</span><h1>{_esc_text(l,f"{prefix}.title")}</h1><p>{_esc_text(l,f"{prefix}.lead")}</p></div></section><section class="rp-page"><div class="rp-container rp-legal">{parts}<div class="rp-legal-note">{_esc_text(l,f"{prefix}.disclaimer")}</div></div></section>'''
    return render_public_shell(title=public_text(l,title_key),description=public_text(l,f"{prefix}.lead"),lang=l,content_html=content,active="",language_urls=language_urls)


def render_contact_page(lang: str, contact_email: str = "", language_urls: Optional[Dict[str, str]] = None) -> str:
    l=normalize_ui_language(lang); email=safe_public_email(contact_email)
    direct_action = f'<a class="rp-button rp-button-secondary" href="mailto:{html.escape(email,quote=True)}">{_esc_text(l,"contact.email_label")}</a>' if email else ''
    direct_text = email if email else public_text(l,"contact.direct_text")
    content=f'''<section class="rp-page-hero"><div class="rp-container"><h1>{_esc_text(l,"contact.title")}</h1><p>{_esc_text(l,"contact.lead")}</p></div></section><section class="rp-page"><div class="rp-container rp-grid-3"><article class="rp-card rp-contact-card"><div><div class="rp-icon">01</div><h3>{_esc_text(l,"contact.new_title")}</h3><p>{_esc_text(l,"contact.new_text")}</p></div><a class="rp-button rp-button-primary" href="/public/signup?ui_lang={l}">{_esc_text(l,"common.open_signup")}</a></article><article class="rp-card rp-contact-card"><div><div class="rp-icon">02</div><h3>{_esc_text(l,"contact.owner_title")}</h3><p>{_esc_text(l,"contact.owner_text")}</p></div><a class="rp-button rp-button-secondary" href="/owner/login?ui_lang={l}">{_esc_text(l,"common.open_login")}</a></article><article class="rp-card rp-contact-card"><div><div class="rp-icon">03</div><h3>{_esc_text(l,"contact.direct_title")}</h3><p>{html.escape(direct_text)}</p></div>{direct_action}</article></div></section>'''
    return render_public_shell(title=public_text(l,"meta.contact"),description=public_text(l,"contact.lead"),lang=l,content_html=content,language_urls=language_urls)


def render_support_page(lang: str, language_urls: Optional[Dict[str, str]] = None) -> str:
    l=normalize_ui_language(lang)
    cards="".join(f'<article class="rp-card"><div class="rp-icon">0{i}</div><h3>{_esc_text(l,f"support.s{i}")}</h3><p>{_esc_text(l,f"support.s{i}_text")}</p></article>' for i in range(1,5))
    content=f'''<section class="rp-page-hero"><div class="rp-container"><h1>{_esc_text(l,"support.title")}</h1><p>{_esc_text(l,"support.lead")}</p></div></section><section class="rp-page"><div class="rp-container"><div class="rp-grid-2">{cards}</div><div class="rp-hero-actions"><a class="rp-button rp-button-primary" href="/owner/login?ui_lang={l}">{_esc_text(l,"support.cta")}</a><a class="rp-button rp-button-secondary" href="/contact?ui_lang={l}">{_esc_text(l,"footer.contact")}</a></div></div></section>'''
    return render_public_shell(title=public_text(l,"meta.support"),description=public_text(l,"support.lead"),lang=l,content_html=content,active="support",language_urls=language_urls)
