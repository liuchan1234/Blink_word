"""
Blink.World — Internationalization (i18n)
Lightweight key-based translation.
Supported: zh (Chinese), en (English), ru (Russian), id (Indonesian), pt (Portuguese)
"""

from typing import Any

SUPPORTED_LANGUAGES = ["zh", "en", "ru", "id", "pt"]

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "English",
    "ru": "Русский",
    "id": "Bahasa Indonesia",
    "pt": "Português",
}

# ── Translation Dictionary ──

_T: dict[str, dict[str, str]] = {
    # ══════════════════════════════════════
    # Onboarding
    # ══════════════════════════════════════
    "welcome": {
        "zh": "👋 欢迎来到 <b>Blink.World</b>！\n\n这里是匿名真实故事平台——讲出在别处不敢说的话，看到在别处看不到的真实世界。",
        "en": "👋 Welcome to <b>Blink.World</b>!\n\nAn anonymous real story platform — share what you can't say elsewhere, see the real world hidden from view.",
        "ru": "👋 Добро пожаловать в <b>Blink.World</b>!\n\nАнонимная платформа реальных историй — расскажи то, что не скажешь в другом месте.",
        "id": "👋 Selamat datang di <b>Blink.World</b>!\n\nPlatform cerita anonim — bagikan apa yang tidak bisa kamu ceritakan di tempat lain.",
        "pt": "👋 Bem-vindo ao <b>Blink.World</b>!\n\nUma plataforma de historias anonimas — compartilhe o que voce nao pode dizer em outro lugar.",
    },
    "choose_country": {
        "zh": "🌍 你在哪个国家？\n\n这会帮我们为你推荐更贴近的内容。",
        "en": "🌍 What country are you in?\n\nThis helps us recommend content closer to you.",
        "ru": "🌍 В какой ты стране?\n\nЭто поможет нам рекомендовать более близкий контент.",
        "id": "🌍 Kamu di negara mana?\n\nIni membantu kami merekomendasikan konten yang lebih dekat denganmu.",
        "pt": "🌍 Em que pais voce esta?\n\nIsso nos ajuda a recomendar conteudo mais proximo de voce.",
    },
    "country_set": {
        "zh": "✅ 已设置为 {country}",
        "en": "✅ Set to {country}",
        "ru": "✅ Установлено: {country}",
        "id": "✅ Diatur ke {country}",
        "pt": "✅ Definido como {country}",
    },
    "setup_complete": {
        "zh": "🎉 设置完成！开始刷故事吧 👇",
        "en": "🎉 All set! Start browsing stories 👇",
        "ru": "🎉 Готово! Начинай листать истории 👇",
        "id": "🎉 Siap! Mulai jelajahi cerita 👇",
        "pt": "🎉 Tudo pronto! Comece a ver historias 👇",
    },

    # ══════════════════════════════════════
    # Main Menu
    # ══════════════════════════════════════
    "menu_browse": {
        "zh": "📖 刷故事",
        "en": "📖 Browse",
        "ru": "📖 Листать",
        "id": "📖 Jelajahi",
        "pt": "📖 Explorar",
    },
    "menu_post": {
        "zh": "📝 说一个",
        "en": "📝 Share",
        "ru": "📝 Рассказать",
        "id": "📝 Ceritakan",
        "pt": "📝 Compartilhar",
    },
    "menu_me": {
        "zh": "👤 我的",
        "en": "👤 Me",
        "ru": "👤 Профиль",
        "id": "👤 Profil",
        "pt": "👤 Perfil",
    },
    "menu_settings": {
        "zh": "⚙️ 设置",
        "en": "⚙️ Settings",
        "ru": "⚙️ Настройки",
        "id": "⚙️ Pengaturan",
        "pt": "⚙️ Config",
    },

    # ══════════════════════════════════════
    # Browsing
    # ══════════════════════════════════════
    "no_more_content": {
        "zh": "📭 当前没有更多内容啦，过会儿再来看看吧！",
        "en": "📭 No more content right now, check back later!",
        "ru": "📭 Пока больше нет контента, загляни позже!",
        "id": "📭 Belum ada konten lagi, cek lagi nanti!",
        "pt": "📭 Sem mais conteudo agora, volte depois!",
    },
    "anonymous": {
        "zh": "匿名",
        "en": "Anonymous",
        "ru": "Аноним",
        "id": "Anonim",
        "pt": "Anonimo",
    },
    "view_original": {
        "zh": "🔤 查看原文",
        "en": "🔤 View original",
        "ru": "🔤 Оригинал",
        "id": "🔤 Lihat asli",
        "pt": "🔤 Ver original",
    },
    "post_also": {
        "zh": "📝 我也说一个",
        "en": "📝 Me too",
        "ru": "📝 Тоже расскажу",
        "id": "📝 Aku juga",
        "pt": "📝 Eu tambem",
    },

    # ══════════════════════════════════════
    # Reactions
    # ══════════════════════════════════════
    "reaction_already": {
        "zh": "你已经对这条内容反应过了",
        "en": "You've already reacted to this",
        "ru": "Ты уже реагировал на это",
        "id": "Kamu sudah bereaksi",
        "pt": "Voce ja reagiu a isso",
    },

    # ══════════════════════════════════════
    # Swipe Actions
    # ══════════════════════════════════════
    "liked": {"zh": "👍", "en": "👍", "ru": "👍", "id": "👍", "pt": "👍"},
    "disliked": {"zh": "👎", "en": "👎", "ru": "👎", "id": "👎", "pt": "👎"},
    "favorited": {
        "zh": "⭐ 已收藏",
        "en": "⭐ Saved",
        "ru": "⭐ Сохранено",
        "id": "⭐ Disimpan",
        "pt": "⭐ Salvo",
    },
    "reported": {
        "zh": "⚠️ 已举报，感谢反馈",
        "en": "⚠️ Reported, thanks for the feedback",
        "ru": "⚠️ Жалоба отправлена, спасибо",
        "id": "⚠️ Dilaporkan, terima kasih",
        "pt": "⚠️ Denunciado, obrigado",
    },
    "already_favorited": {
        "zh": "已经收藏过了",
        "en": "Already saved",
        "ru": "Уже сохранено",
        "id": "Sudah disimpan",
        "pt": "Ja salvo",
    },
    "unfavorited": {
        "zh": "已取消收藏",
        "en": "Unsaved",
        "ru": "Удалено из избранного",
        "id": "Dihapus dari simpanan",
        "pt": "Removido dos salvos",
    },

    # ══════════════════════════════════════
    # Publishing
    # ══════════════════════════════════════
    "choose_channel": {
        "zh": "选择一个频道发布你的故事：",
        "en": "Choose a channel for your story:",
        "ru": "Выбери канал для своей истории:",
        "id": "Pilih saluran untuk ceritamu:",
        "pt": "Escolha um canal para sua historia:",
    },
    "enter_content": {
        "zh": "📝 写下你的故事（30-500字）\n\n可以发送纯文字，也可以发一张图+文字。",
        "en": "📝 Write your story (30-500 characters)\n\nYou can send text only, or an image + text.",
        "ru": "📝 Напиши свою историю (30-500 символов)\n\nМожно отправить текст или фото + текст.",
        "id": "📝 Tulis ceritamu (30-500 karakter)\n\nBisa kirim teks saja, atau foto + teks.",
        "pt": "📝 Escreva sua historia (30-500 caracteres)\n\nVoce pode enviar texto ou foto + texto.",
    },
    "content_too_short": {
        "zh": "⚠️ 内容太短了，至少需要 30 个字",
        "en": "⚠️ Too short, minimum 30 characters",
        "ru": "⚠️ Слишком коротко, минимум 30 символов",
        "id": "⚠️ Terlalu pendek, minimal 30 karakter",
        "pt": "⚠️ Muito curto, minimo 30 caracteres",
    },
    "content_too_long": {
        "zh": "⚠️ 内容太长了，最多 500 个字",
        "en": "⚠️ Too long, maximum 500 characters",
        "ru": "⚠️ Слишком длинно, максимум 500 символов",
        "id": "⚠️ Terlalu panjang, maksimal 500 karakter",
        "pt": "⚠️ Muito longo, maximo 500 caracteres",
    },
    "preview_confirm": {
        "zh": "预览你的故事 👆\n\n确认发布吗？",
        "en": "Preview your story 👆\n\nConfirm publish?",
        "ru": "Предпросмотр 👆\n\nОпубликовать?",
        "id": "Pratinjau ceritamu 👆\n\nKonfirmasi publikasi?",
        "pt": "Pre-visualizacao 👆\n\nConfirmar publicacao?",
    },
    "publish_confirm_btn": {
        "zh": "✅ 确认发布",
        "en": "✅ Confirm",
        "ru": "✅ Опубликовать",
        "id": "✅ Konfirmasi",
        "pt": "✅ Confirmar",
    },
    "publish_cancel_btn": {
        "zh": "❌ 取消",
        "en": "❌ Cancel",
        "ru": "❌ Отмена",
        "id": "❌ Batal",
        "pt": "❌ Cancelar",
    },
    "publish_to_world": {
        "zh": "🌍 发到全世界",
        "en": "🌍 Share globally",
        "ru": "🌍 Для всех",
        "id": "🌍 Bagikan ke semua",
        "pt": "🌍 Compartilhar globalmente",
    },
    "publish_to_group": {
        "zh": "🔒 只发到群里",
        "en": "🔒 Group only",
        "ru": "🔒 Только в группу",
        "id": "🔒 Grup saja",
        "pt": "🔒 Somente no grupo",
    },
    "published_success": {
        "zh": "✅ 发布成功！你的故事已经上线了",
        "en": "✅ Published! Your story is live",
        "ru": "✅ Опубликовано! Твоя история уже онлайн",
        "id": "✅ Dipublikasikan! Ceritamu sudah tayang",
        "pt": "✅ Publicado! Sua historia esta no ar",
    },
    "publish_cancelled": {
        "zh": "已取消",
        "en": "Cancelled",
        "ru": "Отменено",
        "id": "Dibatalkan",
        "pt": "Cancelado",
    },

    # ══════════════════════════════════════
    # Daily Topic
    # ══════════════════════════════════════
    "daily_topic_hint": {
        "zh": "📮 今日话题：{topic}\n\n回答今日话题可额外获得 10 积分！",
        "en": "📮 Today's topic: {topic}\n\nAnswer today's topic for 10 bonus points!",
        "ru": "📮 Тема дня: {topic}\n\nОтветь на тему дня и получи 10 бонусных баллов!",
        "id": "📮 Topik hari ini: {topic}\n\nJawab topik hari ini untuk 10 poin bonus!",
        "pt": "📮 Topico de hoje: {topic}\n\nResponda e ganhe 10 pontos bonus!",
    },

    # ══════════════════════════════════════
    # Group
    # ══════════════════════════════════════
    "group_welcome": {
        "zh": "👋 大家好！我是 Blink.World Bot\n\n发送 /blink 开始一起刷故事！",
        "en": "👋 Hello everyone! I'm Blink.World Bot\n\nSend /blink to start browsing stories together!",
        "ru": "👋 Всем привет! Я Blink.World Bot\n\nОтправьте /blink чтобы листать истории вместе!",
        "id": "👋 Halo semua! Saya Blink.World Bot\n\nKirim /blink untuk mulai jelajahi cerita bersama!",
        "pt": "👋 Ola a todos! Sou o Blink.World Bot\n\nEnvie /blink para explorar historias juntos!",
    },
    "group_rate_limited": {
        "zh": "⏳ 慢一点，{seconds}秒后再试",
        "en": "⏳ Slow down, try again in {seconds}s",
        "ru": "⏳ Подожди {seconds} сек",
        "id": "⏳ Pelan-pelan, coba lagi dalam {seconds} detik",
        "pt": "⏳ Devagar, tente novamente em {seconds}s",
    },
    "group_summary_title": {
        "zh": "📊 今日群组摘要",
        "en": "📊 Today's Group Summary",
        "ru": "📊 Итоги дня в группе",
        "id": "📊 Ringkasan Grup Hari Ini",
        "pt": "📊 Resumo do Grupo Hoje",
    },
    "group_summary_header": {
        "zh": "📊 <b>今日群组摘要</b>",
        "en": "📊 <b>Today's Group Summary</b>",
        "ru": "📊 <b>Итоги дня в группе</b>",
        "id": "📊 <b>Ringkasan Grup Hari Ini</b>",
        "pt": "📊 <b>Resumo do Grupo Hoje</b>",
    },
    "group_summary_swipes": {
        "zh": "🔄 今日刷卡: {count} 张",
        "en": "🔄 Cards today: {count}",
        "ru": "🔄 Карточек сегодня: {count}",
        "id": "🔄 Kartu hari ini: {count}",
        "pt": "🔄 Cards hoje: {count}",
    },
    "group_summary_posters": {
        "zh": "📝 匿名大字报: {count} 条",
        "en": "📝 Anonymous posts: {count}",
        "ru": "📝 Анонимных постов: {count}",
        "id": "📝 Postingan anonim: {count}",
        "pt": "📝 Posts anonimos: {count}",
    },
    "group_summary_top": {
        "zh": "🏆 最热卡片 ({count} 个表情):",
        "en": "🏆 Top card ({count} reactions):",
        "ru": "🏆 Топ карточка ({count} реакций):",
        "id": "🏆 Kartu terpopuler ({count} reaksi):",
        "pt": "🏆 Card mais popular ({count} reacoes):",
    },
    "group_summary_cta": {
        "zh": "明天继续！发送 /blink 开始刷故事 🚀",
        "en": "See you tomorrow! Send /blink to start 🚀",
        "ru": "До завтра! Отправь /blink 🚀",
        "id": "Sampai besok! Kirim /blink 🚀",
        "pt": "Ate amanha! Envie /blink 🚀",
    },

    # ══════════════════════════════════════
    # Points & Milestones
    # ══════════════════════════════════════
    "checkin_success": {
        "zh": "✅ 签到成功！+{points} 积分\n当前积分：{total}",
        "en": "✅ Checked in! +{points} points\nTotal: {total}",
        "ru": "✅ Отмечено! +{points} баллов\nВсего: {total}",
        "id": "✅ Check-in berhasil! +{points} poin\nTotal: {total}",
        "pt": "✅ Check-in feito! +{points} pontos\nTotal: {total}",
    },
    "checkin_already": {
        "zh": "⚠️ 今天已经签到过了，明天再来吧！",
        "en": "⚠️ Already checked in today, come back tomorrow!",
        "ru": "⚠️ Ты уже отмечался сегодня, приходи завтра!",
        "id": "⚠️ Sudah check-in hari ini, datang lagi besok!",
        "pt": "⚠️ Ja fez check-in hoje, volte amanha!",
    },
    "milestone_10": {
        "zh": "🎉 你的故事引起了 10 个人的共鸣！+10 积分",
        "en": "🎉 Your story resonated with 10 people! +10 points",
        "ru": "🎉 Твоя история нашла отклик у 10 человек! +10 баллов",
        "id": "🎉 Ceritamu beresonansi dengan 10 orang! +10 poin",
        "pt": "🎉 Sua historia tocou 10 pessoas! +10 pontos",
    },
    "milestone_30": {
        "zh": "🔥 30 个人为你的故事留下了表情！+30 积分",
        "en": "🔥 30 people reacted to your story! +30 points",
        "ru": "🔥 30 человек отреагировали на твою историю! +30 баллов",
        "id": "🔥 30 orang bereaksi pada ceritamu! +30 poin",
        "pt": "🔥 30 pessoas reagiram a sua historia! +30 pontos",
    },
    "milestone_100": {
        "zh": "🔥 你的故事火了！+100 积分",
        "en": "🔥 Your story is on fire! +100 points",
        "ru": "🔥 Твоя история в огне! +100 баллов",
        "id": "🔥 Ceritamu viral! +100 poin",
        "pt": "🔥 Sua historia bombou! +100 pontos",
    },
    "milestone_300": {
        "zh": "🏆 传奇故事！+300 积分",
        "en": "🏆 Legendary story! +300 points",
        "ru": "🏆 Легендарная история! +300 баллов",
        "id": "🏆 Cerita legendaris! +300 poin",
        "pt": "🏆 Historia lendaria! +300 pontos",
    },
    "milestone_1000": {
        "zh": "👑 现象级创作！+1000 积分",
        "en": "👑 Phenomenal creation! +1000 points",
        "ru": "👑 Феноменальное творение! +1000 баллов",
        "id": "👑 Kreasi fenomenal! +1000 poin",
        "pt": "👑 Criacao fenomenal! +1000 pontos",
    },

    # ══════════════════════════════════════
    # Invite
    # ══════════════════════════════════════
    "invite_success": {
        "zh": "🎉 邀请成功！+{points} 积分",
        "en": "🎉 Invite successful! +{points} points",
        "ru": "🎉 Приглашение принято! +{points} баллов",
        "id": "🎉 Undangan berhasil! +{points} poin",
        "pt": "🎉 Convite aceito! +{points} pontos",
    },
    "invite_link": {
        "zh": "🔗 你的邀请链接：\n{link}\n\n每成功邀请一人 +50 积分！",
        "en": "🔗 Your invite link:\n{link}\n\n+50 points per invite!",
        "ru": "🔗 Твоя ссылка:\n{link}\n\n+50 баллов за приглашение!",
        "id": "🔗 Link undanganmu:\n{link}\n\n+50 poin per undangan!",
        "pt": "🔗 Seu link de convite:\n{link}\n\n+50 pontos por convite!",
    },

    # ══════════════════════════════════════
    # Settings
    # ══════════════════════════════════════
    "settings_title": {
        "zh": "⚙️ 设置",
        "en": "⚙️ Settings",
        "ru": "⚙️ Настройки",
        "id": "⚙️ Pengaturan",
        "pt": "⚙️ Configuracoes",
    },
    "settings_language": {
        "zh": "🌐 语言",
        "en": "🌐 Language",
        "ru": "🌐 Язык",
        "id": "🌐 Bahasa",
        "pt": "🌐 Idioma",
    },
    "settings_country": {
        "zh": "📍 国家",
        "en": "📍 Country",
        "ru": "📍 Страна",
        "id": "📍 Negara",
        "pt": "📍 Pais",
    },
    "settings_channels": {
        "zh": "📺 频道订阅",
        "en": "📺 Channels",
        "ru": "📺 Каналы",
        "id": "📺 Saluran",
        "pt": "📺 Canais",
    },
    "settings_show_country": {
        "zh": "📍 发帖显示位置",
        "en": "📍 Show location on posts",
        "ru": "📍 Показывать страну в постах",
        "id": "📍 Tampilkan lokasi di postingan",
        "pt": "📍 Mostrar localizacao nos posts",
    },
    "lang_changed": {
        "zh": "✅ 语言已切换为中文",
        "en": "✅ Language changed to English",
        "ru": "✅ Язык изменен на русский",
        "id": "✅ Bahasa diubah ke Indonesia",
        "pt": "✅ Idioma alterado para Portugues",
    },

    # ══════════════════════════════════════
    # Errors
    # ══════════════════════════════════════
    "error_generic": {
        "zh": "⚠️ 出了点问题，请稍后重试",
        "en": "⚠️ Something went wrong, please try again",
        "ru": "⚠️ Что-то пошло не так, попробуй позже",
        "id": "⚠️ Ada yang salah, coba lagi nanti",
        "pt": "⚠️ Algo deu errado, tente novamente",
    },
    "error_not_found": {
        "zh": "⚠️ 内容不存在或已下架",
        "en": "⚠️ Content not found or removed",
        "ru": "⚠️ Контент не найден или удален",
        "id": "⚠️ Konten tidak ditemukan atau dihapus",
        "pt": "⚠️ Conteudo nao encontrado ou removido",
    },

    # ══════════════════════════════════════
    # Creator Panel
    # ══════════════════════════════════════
    "my_stories_title": {
        "zh": "📊 <b>我的故事</b>",
        "en": "📊 <b>My Stories</b>",
        "ru": "📊 <b>Мои истории</b>",
        "id": "📊 <b>Cerita Saya</b>",
        "pt": "📊 <b>Minhas Historias</b>",
    },
    "no_stories_yet": {
        "zh": "你还没有发布过故事",
        "en": "You haven't published any stories yet",
        "ru": "Ты ещё не публиковал историй",
        "id": "Kamu belum mempublikasikan cerita",
        "pt": "Voce ainda nao publicou historias",
    },
    "my_favorites_title": {
        "zh": "⭐ <b>我的收藏</b>",
        "en": "⭐ <b>Saved Stories</b>",
        "ru": "⭐ <b>Избранное</b>",
        "id": "⭐ <b>Cerita Tersimpan</b>",
        "pt": "⭐ <b>Historias Salvas</b>",
    },
    "no_favorites_yet": {
        "zh": "你还没有收藏过内容",
        "en": "No saved stories yet",
        "ru": "Пока ничего не сохранено",
        "id": "Belum ada cerita yang disimpan",
        "pt": "Nenhuma historia salva ainda",
    },
    "btn_my_stories": {
        "zh": "📊 我的故事",
        "en": "📊 My Stories",
        "ru": "📊 Мои истории",
        "id": "📊 Cerita Saya",
        "pt": "📊 Minhas Historias",
    },
    "btn_my_favorites": {
        "zh": "⭐ 我的收藏",
        "en": "⭐ Saved",
        "ru": "⭐ Избранное",
        "id": "⭐ Tersimpan",
        "pt": "⭐ Salvos",
    },

    # ══════════════════════════════════════
    # Country input
    # ══════════════════════════════════════
    "country_input_hint": {
        "zh": "🌍 你在哪个国家？\n\n点击下方按钮快速选择，或者<b>直接输入你的国家名称</b>（支持任何语言）。",
        "en": "🌍 What country are you in?\n\nTap a button below, or <b>type your country name</b> in any language.",
        "ru": "🌍 В какой ты стране?\n\nНажми кнопку или <b>напиши название страны</b> на любом языке.",
        "id": "🌍 Kamu di negara mana?\n\nTekan tombol atau <b>ketik nama negaramu</b> dalam bahasa apa saja.",
        "pt": "🌍 Em que pais voce esta?\n\nToque em um botao ou <b>digite o nome do pais</b> em qualquer idioma.",
    },
    "country_change_hint": {
        "zh": "🌍 选择或输入你的国家（支持任何语言）：",
        "en": "🌍 Pick or type your country (any language):",
        "ru": "🌍 Выбери или напиши свою страну (любой язык):",
        "id": "🌍 Pilih atau ketik negaramu (bahasa apa saja):",
        "pt": "🌍 Escolha ou digite seu pais (qualquer idioma):",
    },
}


# ══════════════════════════════════════
# Core Functions
# ══════════════════════════════════════

def t(key: str, lang: str = "zh", **kwargs: Any) -> str:
    """
    Get translated string by key.
    Falls back: requested lang → en → key itself.
    Supports {placeholder} substitution.
    """
    entry = _T.get(key)
    if entry is None:
        return key

    text = entry.get(lang) or entry.get("en") or key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return text


def detect_language(language_code: str | None) -> str:
    """Detect user language from Telegram language_code. Falls back to en."""
    if not language_code:
        return "en"
    code = language_code.lower()[:2]
    mapping = {
        "zh": "zh",
        "ru": "ru",
        "id": "id",  # Indonesian
        "in": "id",  # Some Telegram clients send "in" for Indonesian
        "pt": "pt",
        "en": "en",
    }
    return mapping.get(code, "en")


def guess_country(language_code: str | None) -> str:
    """Guess default country from language code."""
    if not language_code:
        return ""
    code = language_code.lower()[:2]
    mapping = {
        "zh": "中国",
        "ru": "俄罗斯",
        "id": "印尼",
        "in": "印尼",
        "pt": "巴西",
        "en": "United States",
        "ja": "日本",
        "ko": "韩国",
        "es": "西班牙",
        "fr": "法国",
        "de": "德国",
        "ar": "沙特阿拉伯",
        "hi": "印度",
    }
    return mapping.get(code, "")
