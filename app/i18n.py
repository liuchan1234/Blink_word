"""
Blink.World — Internationalization (i18n)
Lightweight key-based translation.
Supported: zh (Chinese), en (English), ru (Russian), id (Indonesian), pt (Portuguese)

NATIVE-FIRST: Every language is written as a native speaker would naturally say it,
not as a literal translation from Chinese.
"""

from typing import Any

SUPPORTED_LANGUAGES = ["en", "ru", "pt", "id", "zh"]

LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
    "pt": "Português",
    "id": "Bahasa Indonesia",
    "zh": "中文",
}

_T: dict[str, dict[str, str]] = {
    "welcome": {
        "zh": "👋 欢迎来到 <b>Blink.World</b>！\n\n这里是匿名真实故事平台——讲出在别处不敢说的话，看到在别处看不到的真实世界。",
        "en": "👋 Welcome to <b>Blink.World</b>!\n\nReal stories, zero filters — say what you'd never say out loud, and peek into lives you'd never see.",
        "ru": "👋 Добро пожаловать в <b>Blink.World</b>!\n\nНастоящие истории без фильтров — расскажи то, что вслух не скажешь, и загляни в чужие жизни.",
        "id": "👋 Selamat datang di <b>Blink.World</b>!\n\nCerita nyata, tanpa topeng — curhat yang nggak bisa kamu bilang ke siapa pun, dan intip kehidupan orang lain.",
        "pt": "👋 Bem-vindo ao <b>Blink.World</b>!\n\nHistórias reais, sem filtro — desabafe o que não dá pra falar em voz alta e espie vidas que você nunca veria.",
    },
    "choose_country": {"zh": "🌍 你在哪个国家？\n\n这会帮我们为你推荐更贴近的内容。", "en": "🌍 Where are you based?\n\nThis helps us show you stories that hit closer to home.", "ru": "🌍 Откуда ты?\n\nТак мы покажем истории, которые тебе ближе.", "id": "🌍 Kamu dari mana?\n\nBiar kita kasih cerita yang lebih nyambung buatmu.", "pt": "🌍 De onde você é?\n\nAssim a gente mostra histórias mais próximas de você."},
    "onboard_country_hint": {"zh": "🌍 你在哪个国家？\n\n点击下方按钮快速选择，或者<b>直接输入你的国家名称</b>（支持任何语言）。", "en": "🌍 Where are you based?\n\nTap a button below or just <b>type your country</b> in any language.", "ru": "🌍 Откуда ты?\n\nНажми кнопку или просто <b>напиши свою страну</b> на любом языке.", "id": "🌍 Kamu dari mana?\n\nKetuk tombol di bawah atau langsung <b>ketik nama negaramu</b> pakai bahasa apa aja.", "pt": "🌍 De onde você é?\n\nToque num botão abaixo ou simplesmente <b>digite seu país</b> em qualquer idioma."},
    "country_set": {"zh": "✅ 已设置为 {country}", "en": "✅ Got it — {country}", "ru": "✅ Принято — {country}", "id": "✅ Oke — {country}", "pt": "✅ Beleza — {country}"},
    "setup_complete": {"zh": "🎉 设置完成！开始刷故事吧 👇", "en": "🎉 You're all set! Start swiping through stories 👇", "ru": "🎉 Готово! Давай листать истории 👇", "id": "🎉 Siap! Yuk mulai geser-geser cerita 👇", "pt": "🎉 Tudo pronto! Bora ver as histórias 👇"},
    "onboard_intro": {
        "zh": (
            "🌍 <b>200 个国家，一个树洞。</b>\n\n"
            "这里每个人都是匿名的。\n"
            "你会看到世界各地真实的人，讲出他们在别处不敢说的话。\n\n"
            "👇 <b>怎么玩</b>\n"
            "📖 <b>刷</b> — 左滑右滑，看别人的故事\n"
            "📝 <b>写</b> — 匿名讲出你自己的\n"
            "👥 <b>群</b> — 拉进群聊，和朋友一起刷\n\n"
            "试试看 👇 这是你的第一个故事"
        ),
        "en": (
            "🌍 <b>200 countries. One place to be real.</b>\n\n"
            "Everyone here is anonymous.\n"
            "You'll read what people across the world would never say out loud.\n\n"
            "👇 <b>How it works</b>\n"
            "📖 <b>Swipe</b> — flip through real stories\n"
            "📝 <b>Write</b> — share yours, anonymously\n"
            "👥 <b>Group</b> — add to a group chat, swipe with friends\n\n"
            "Here's your first story 👇"
        ),
        "ru": (
            "🌍 <b>200 стран. Одно место, где можно быть настоящим.</b>\n\n"
            "Тут все анонимы.\n"
            "Ты прочитаешь то, что люди со всего мира никогда бы не сказали вслух.\n\n"
            "👇 <b>Как это работает</b>\n"
            "📖 <b>Листай</b> — реальные истории\n"
            "📝 <b>Пиши</b> — расскажи свою, анонимно\n"
            "👥 <b>Группа</b> — добавь в чат, листайте вместе\n\n"
            "Вот твоя первая история 👇"
        ),
        "id": (
            "🌍 <b>200 negara. Satu tempat buat jadi nyata.</b>\n\n"
            "Semua orang di sini anonim.\n"
            "Kamu bakal baca apa yang orang dari seluruh dunia nggak berani bilang.\n\n"
            "👇 <b>Cara mainnya</b>\n"
            "📖 <b>Geser</b> — baca cerita nyata\n"
            "📝 <b>Tulis</b> — ceritain punyamu, anonim\n"
            "👥 <b>Grup</b> — tambahin ke grup, geser bareng\n\n"
            "Ini cerita pertamamu 👇"
        ),
        "pt": (
            "🌍 <b>200 países. Um lugar pra ser real.</b>\n\n"
            "Todo mundo aqui é anônimo.\n"
            "Você vai ler o que pessoas do mundo todo nunca diriam em voz alta.\n\n"
            "👇 <b>Como funciona</b>\n"
            "📖 <b>Deslize</b> — histórias reais\n"
            "📝 <b>Escreva</b> — conte a sua, anonimamente\n"
            "👥 <b>Grupo</b> — adicione num grupo, vejam juntos\n\n"
            "Aqui tá sua primeira história 👇"
        ),
    },
    "menu_browse": {"zh": "📖 刷故事", "en": "📖 Stories", "ru": "📖 Истории", "id": "📖 Cerita", "pt": "📖 Histórias"},
    "menu_post": {"zh": "📝 说一个", "en": "📝 Write", "ru": "📝 Написать", "id": "📝 Tulis", "pt": "📝 Escrever"},
    "menu_me": {"zh": "👤 我的", "en": "👤 Me", "ru": "👤 Я", "id": "👤 Aku", "pt": "👤 Eu"},
    "menu_settings": {"zh": "⚙️ 设置", "en": "⚙️ Settings", "ru": "⚙️ Настройки", "id": "⚙️ Setelan", "pt": "⚙️ Config"},
    "menu_group": {"zh": "👥 群聊天", "en": "👥 Group Chat", "ru": "👥 Группа", "id": "👥 Grup", "pt": "👥 Grupo"},
    "browse_like_btn": {"zh": "👍 赞", "en": "👍 Like", "ru": "👍 Ок", "id": "👍 Suka", "pt": "👍 Curti"},
    "browse_next_btn": {"zh": "👎 下一个", "en": "👎 Next", "ru": "👎 Дальше", "id": "👎 Lewat", "pt": "👎 Próx"},
    "browse_favorite_btn": {"zh": "⭐ 收藏", "en": "⭐ Save", "ru": "⭐ Сохранить", "id": "⭐ Simpan", "pt": "⭐ Salvar"},
    "browse_report_btn": {"zh": "⚠️ 举报", "en": "⚠️ Report", "ru": "⚠️ Жалоба", "id": "⚠️ Lapor", "pt": "⚠️ Denúncia"},
    "browse_back_btn": {"zh": "↩️ 返回", "en": "↩️ Back", "ru": "↩️ Назад", "id": "↩️ Kembali", "pt": "↩️ Voltar"},
    "browse_topics_btn": {"zh": "🎯 主题", "en": "🎯 Topics", "ru": "🎯 Темы", "id": "🎯 Topik", "pt": "🎯 Temas"},
    "group_topics_header": {"zh": "🎯 当前群频道（点击切换）", "en": "🎯 Pick what you wanna see (tap to toggle)", "ru": "🎯 Выбери, что хочешь видеть (нажми для переключения)", "id": "🎯 Pilih yang mau kamu lihat (ketuk buat ganti)", "pt": "🎯 Escolha o que quer ver (toque pra alternar)"},
    "group_topics_start": {"zh": "📖 开始刷", "en": "📖 Let's go", "ru": "📖 Погнали", "id": "📖 Gas", "pt": "📖 Bora"},
    "no_more_content": {"zh": "📭 当前没有更多内容啦，过会儿再来看看吧！", "en": "📭 That's all for now — come back for fresh stories later!", "ru": "📭 Пока всё — заходи позже за новыми историями!", "id": "📭 Udah habis buat sekarang — balik lagi nanti ya!", "pt": "📭 Por enquanto é isso — volte depois pra mais histórias!"},
    "anonymous": {"zh": "匿名", "en": "Anonymous", "ru": "Аноним", "id": "Anonim", "pt": "Anônimo"},
    "view_original": {"zh": "🔤 查看原文", "en": "🔤 Original", "ru": "🔤 Оригинал", "id": "🔤 Asli", "pt": "🔤 Original"},
    "post_also": {"zh": "📝 我也说一个", "en": "📝 I've got one", "ru": "📝 У меня тоже", "id": "📝 Gue juga punya", "pt": "📝 Tenho uma"},
    "reaction_already": {"zh": "你已经对这条内容反应过了", "en": "You already reacted to this one", "ru": "Ты уже ставил реакцию на это", "id": "Kamu udah kasih reaksi ke ini", "pt": "Você já reagiu a essa"},
    "liked": {"zh": "👍", "en": "👍", "ru": "👍", "id": "👍", "pt": "👍"},
    "disliked": {"zh": "👎", "en": "👎", "ru": "👎", "id": "👎", "pt": "👎"},
    "favorited": {"zh": "⭐ 已收藏", "en": "⭐ Saved!", "ru": "⭐ Сохранено!", "id": "⭐ Tersimpan!", "pt": "⭐ Salvo!"},
    "reported": {"zh": "⚠️ 已举报，感谢反馈", "en": "⚠️ Reported — thanks for flagging", "ru": "⚠️ Жалоба отправлена — спасибо", "id": "⚠️ Dilaporkan — makasih ya", "pt": "⚠️ Denunciado — valeu pelo aviso"},
    "already_favorited": {"zh": "已经收藏过了", "en": "Already saved", "ru": "Уже сохранено", "id": "Udah disimpan", "pt": "Já tá salvo"},
    "unfavorited": {"zh": "已取消收藏", "en": "Removed from saved", "ru": "Убрано из сохранённых", "id": "Dihapus dari simpanan", "pt": "Removido dos salvos"},
    "reaction_limit": {"zh": "每条内容最多 {max} 个表情", "en": "You can drop up to {max} emojis per story", "ru": "Можно поставить до {max} реакций на историю", "id": "Maksimal {max} emoji per cerita", "pt": "Máximo de {max} reações por história"},
    "browse_rate_limited": {"zh": "⏳ 刷太快了，休息一下吧", "en": "⏳ Whoa, slow down a sec", "ru": "⏳ Полегче, не так быстро", "id": "⏳ Santai, jangan buru-buru", "pt": "⏳ Calma, devagar aí"},
    "share_via_dm": {"zh": "📝 投稿请私聊我：", "en": "📝 To write a story, DM me:", "ru": "📝 Чтобы написать историю, напиши мне:", "id": "📝 Mau nulis cerita? Chat aku:", "pt": "📝 Pra escrever uma história, me chama:"},
    "profile_via_dm": {"zh": "👤 个人资料请私聊查看：", "en": "👤 Check your profile in DM:", "ru": "👤 Твой профиль — в личке:", "id": "👤 Cek profilmu lewat chat:", "pt": "👤 Veja seu perfil no privado:"},
    "already_in_group": {"zh": "✅ 你已经在群聊里了，直接点「刷故事」即可。", "en": "✅ You're already here! Just hit Stories to keep going.", "ru": "✅ Ты уже тут! Жми Истории и вперёд.", "id": "✅ Kamu udah di sini! Langsung ketuk Cerita aja.", "pt": "✅ Você já tá aqui! Só tocar em Histórias pra continuar."},
    "channel_settings_saved": {"zh": "✅ 频道设置已保存", "en": "✅ Channels updated", "ru": "✅ Каналы обновлены", "id": "✅ Channel diperbarui", "pt": "✅ Canais atualizados"},
    "channel_select_title": {"zh": "📺 选择你想看的频道\n\n点击开关，选完点「完成」👇", "en": "📺 Pick the channels you wanna see\n\nToggle on/off, then hit Done 👇", "ru": "📺 Выбери каналы, которые хочешь видеть\n\nВключай-выключай, потом нажми Готово 👇", "id": "📺 Pilih channel yang mau kamu lihat\n\nHidup-matikan, lalu tekan Selesai 👇", "pt": "📺 Escolha os canais que quer ver\n\nAlterne ligado/desligado, depois toque em Pronto 👇"},
    "channel_select_done": {"zh": "✅ 完成", "en": "✅ Done", "ru": "✅ Готово", "id": "✅ Selesai", "pt": "✅ Pronto"},
    "channel_select_min": {"zh": "至少选一个频道", "en": "Keep at least one channel on", "ru": "Оставь хотя бы один канал", "id": "Sisakan minimal satu channel", "pt": "Mantenha pelo menos um canal ligado"},
    "country_not_set": {"zh": "未设置", "en": "Not set", "ru": "Не задано", "id": "Belum diatur", "pt": "Não definido"},
    "milestone_push_body": {"zh": "{milestone}\n\n📊 总互动: <b>{total}</b>\n💰 积分 +{points}（当前: {current}）\n\n继续创作吧！更多人在等着你的故事 ✨", "en": "{milestone}\n\n📊 Total interactions: <b>{total}</b>\n💰 +{points} pts (Total: {current})\n\nKeep going — people are reading ✨", "ru": "{milestone}\n\n📊 Всего взаимодействий: <b>{total}</b>\n💰 +{points} баллов (Всего: {current})\n\nПродолжай — тебя читают ✨", "id": "{milestone}\n\n📊 Total interaksi: <b>{total}</b>\n💰 +{points} poin (Total: {current})\n\nLanjutin — orang-orang baca ceritamu ✨", "pt": "{milestone}\n\n📊 Total de interações: <b>{total}</b>\n💰 +{points} pts (Total: {current})\n\nContinua — tão lendo suas histórias ✨"},
    "milestone_browse_btn": {"zh": "📖 看故事", "en": "📖 Read more", "ru": "📖 Читать", "id": "📖 Baca lagi", "pt": "📖 Ler mais"},
    "milestone_post_btn": {"zh": "📝 再写一个", "en": "📝 Write another", "ru": "📝 Написать ещё", "id": "📝 Tulis lagi", "pt": "📝 Escrever outra"},
    "settings_choose_country": {"zh": "🌍 选择或输入你的国家（支持任何语言）：", "en": "🌍 Pick or type your country (any language):", "ru": "🌍 Выбери или напиши свою страну (любой язык):", "id": "🌍 Pilih atau ketik negaramu (bahasa apa aja):", "pt": "🌍 Escolha ou digite seu país (qualquer idioma):"},
    "settings_open_hint": {"zh": "⚙️ 点击下方按钮打开设置", "en": "⚙️ Tap below to open settings", "ru": "⚙️ Нажми ниже для настроек", "id": "⚙️ Ketuk di bawah buat buka setelan", "pt": "⚙️ Toque abaixo pra abrir configurações"},
    "activated_back_to_group": {"zh": "✅ 已激活！现在回到群里继续刷故事吧 👆", "en": "✅ You're in! Head back to the group 👆", "ru": "✅ Готово! Возвращайся в группу 👆", "id": "✅ Udah aktif! Balik ke grup yuk 👆", "pt": "✅ Ativado! Volta pro grupo 👆"},
    "group_add_reward": {"zh": "🎉 你将 Bot 拉入了群组「{title}」，获得 +{points} 积分！", "en": "🎉 You added the Bot to \"{title}\" — +{points} pts!", "ru": "🎉 Ты добавил бота в «{title}» — +{points} баллов!", "id": "🎉 Bot ditambahkan ke \"{title}\" — +{points} poin!", "pt": "🎉 Bot adicionado ao \"{title}\" — +{points} pts!"},
    "profile_header": {
        "zh": "👤 <b>我的资料</b>\n\n🆔 ID: <code>{user_id}</code>\n🌍 国家: {country}\n🏆 积分: <b>{points}</b>\n\n—— 数据统计 ——\n👁 累计浏览: {views}\n📝 累计发布: {published}\n❤️ 获得喜欢: {likes}\n👥 邀请人数: {invited}\n\n—— 邀请好友 ——\n🔗 {invite_link}\n<i>每成功邀请一人 +{invite_points} 积分</i>",
        "en": "👤 <b>My Profile</b>\n\n🆔 ID: <code>{user_id}</code>\n🌍 Country: {country}\n🏆 Points: <b>{points}</b>\n\n—— Stats ——\n👁 Total views: {views}\n📝 Published: {published}\n❤️ Likes received: {likes}\n👥 Invited: {invited}\n\n—— Invite Friends ——\n🔗 {invite_link}\n<i>+{invite_points} points per invite</i>",
        "ru": "👤 <b>Мой профиль</b>\n\n🆔 ID: <code>{user_id}</code>\n🌍 Страна: {country}\n🏆 Баллы: <b>{points}</b>\n\n—— Статистика ——\n👁 Просмотрено: {views}\n📝 Опубликовано: {published}\n❤️ Получено лайков: {likes}\n👥 Приглашено: {invited}\n\n—— Пригласить друзей ——\n🔗 {invite_link}\n<i>+{invite_points} баллов за приглашение</i>",
        "id": "👤 <b>Profil Saya</b>\n\n🆔 ID: <code>{user_id}</code>\n🌍 Negara: {country}\n🏆 Poin: <b>{points}</b>\n\n—— Statistik ——\n👁 Total dilihat: {views}\n📝 Dipublikasi: {published}\n❤️ Suka diterima: {likes}\n👥 Diundang: {invited}\n\n—— Undang Teman ——\n🔗 {invite_link}\n<i>+{invite_points} poin per undangan</i>",
        "pt": "👤 <b>Meu Perfil</b>\n\n🆔 ID: <code>{user_id}</code>\n🌍 País: {country}\n🏆 Pontos: <b>{points}</b>\n\n—— Estatísticas ——\n👁 Visualizações: {views}\n📝 Publicados: {published}\n❤️ Curtidas: {likes}\n👥 Convidados: {invited}\n\n—— Convidar Amigos ——\n🔗 {invite_link}\n<i>+{invite_points} pontos por convite</i>",
    },
    "settings_header": {"zh": "⚙️ <b>设置</b>\n\n🌐 语言: {lang_name}\n🌍 国家: {country}\n📍 发帖显示位置: {location}", "en": "⚙️ <b>Settings</b>\n\n🌐 Language: {lang_name}\n🌍 Country: {country}\n📍 Show location on posts: {location}", "ru": "⚙️ <b>Настройки</b>\n\n🌐 Язык: {lang_name}\n🌍 Страна: {country}\n📍 Показывать место в постах: {location}", "id": "⚙️ <b>Setelan</b>\n\n🌐 Bahasa: {lang_name}\n🌍 Negara: {country}\n📍 Tampilkan lokasi di postingan: {location}", "pt": "⚙️ <b>Configurações</b>\n\n🌐 Idioma: {lang_name}\n🌍 País: {country}\n📍 Mostrar localização nos posts: {location}"},
    "choose_channel": {"zh": "选择一个频道发布你的故事：", "en": "Pick a channel for your story:", "ru": "Выбери канал для своей истории:", "id": "Pilih channel buat ceritamu:", "pt": "Escolha um canal pra sua história:"},
    "enter_content": {"zh": "📝 写下你的故事（30-500字）\n\n可以发送纯文字，也可以发一张图+文字。", "en": "📝 Write your story (30–500 chars)\n\nText only, or send a photo with a caption.", "ru": "📝 Напиши свою историю (30–500 символов)\n\nМожно текст или фото с подписью.", "id": "📝 Tulis ceritamu (30–500 karakter)\n\nBisa teks aja, atau foto + teks.", "pt": "📝 Escreva sua história (30–500 chars)\n\nSó texto, ou manda uma foto com legenda."},
    "content_too_short": {"zh": "⚠️ 内容太短了，至少需要 {min} 个字", "en": "⚠️ Too short — at least {min} characters", "ru": "⚠️ Слишком коротко — минимум {min} символов", "id": "⚠️ Terlalu pendek — minimal {min} karakter", "pt": "⚠️ Muito curto — mínimo {min} caracteres"},
    "content_too_long": {"zh": "⚠️ 内容太长了，最多 500 个字", "en": "⚠️ Too long — 500 characters max", "ru": "⚠️ Слишком длинно — максимум 500 символов", "id": "⚠️ Terlalu panjang — maksimal 500 karakter", "pt": "⚠️ Muito longo — máximo 500 caracteres"},
    "preview_confirm": {"zh": "预览你的故事 👆\n\n确认发布吗？", "en": "Here's your preview 👆\n\nReady to post?", "ru": "Вот предпросмотр 👆\n\nПубликуем?", "id": "Ini preview-nya 👆\n\nJadi posting?", "pt": "Aqui tá o preview 👆\n\nBora publicar?"},
    "publish_confirm_btn": {"zh": "✅ 确认发布", "en": "✅ Post it", "ru": "✅ Опубликовать", "id": "✅ Posting", "pt": "✅ Publicar"},
    "publish_cancel_btn": {"zh": "❌ 取消", "en": "❌ Nah, cancel", "ru": "❌ Отмена", "id": "❌ Batal", "pt": "❌ Cancelar"},
    "publish_to_world": {"zh": "🌍 发到全世界", "en": "🌍 Go public", "ru": "🌍 Для всех", "id": "🌍 Publik", "pt": "🌍 Público"},
    "publish_to_group": {"zh": "🔒 只发到群里", "en": "🔒 Group only", "ru": "🔒 Только в группу", "id": "🔒 Grup aja", "pt": "🔒 Só no grupo"},
    "published_success": {"zh": "✅ 发布成功！你的故事已经上线了", "en": "✅ Posted! Your story is live now", "ru": "✅ Опубликовано! Твоя история уже онлайн", "id": "✅ Terposting! Ceritamu udah tayang", "pt": "✅ Publicado! Sua história tá no ar"},
    "publish_cancelled": {"zh": "已取消", "en": "Cancelled", "ru": "Отменено", "id": "Dibatalkan", "pt": "Cancelado"},
    "daily_topic_hint": {"zh": "📮 今日话题：{topic}\n\n回答今日话题可额外获得 10 积分！", "en": "📮 Today's prompt: {topic}\n\nAnswer it for 10 bonus points!", "ru": "📮 Тема дня: {topic}\n\nОтветь и получи 10 бонусных баллов!", "id": "📮 Topik hari ini: {topic}\n\nJawab buat dapet 10 poin bonus!", "pt": "📮 Tema de hoje: {topic}\n\nResponda e ganhe 10 pontos bônus!"},
    "group_welcome": {"zh": "👋 匿名故事来了 👇 点个表情试试 · 发 /world 看更多", "en": "👋 Anonymous stories incoming 👇 Drop an emoji · Send /world for more", "ru": "👋 Анонимные истории 👇 Ткни эмодзи · Отправь /world для продолжения", "id": "👋 Cerita anonim datang 👇 Kasih emoji · Kirim /world buat lanjut", "pt": "👋 Histórias anônimas 👇 Manda um emoji · Envie /world pra mais"},
    "group_rate_limited": {"zh": "⏳ 慢一点，{seconds}秒后再试", "en": "⏳ Easy, try again in {seconds}s", "ru": "⏳ Подожди {seconds} сек", "id": "⏳ Santai, coba lagi {seconds} detik lagi", "pt": "⏳ Calma, tenta de novo em {seconds}s"},
    "group_stopped": {"zh": "⏹ 已暂停。发 /world 重新开始。", "en": "⏹ Bye! Send /world to start again.", "ru": "⏹ Пока! Отправь /world, чтобы начать снова.", "id": "⏹ Sampai jumpa! Kirim /world untuk mulai lagi.", "pt": "⏹ Tchau! Envie /world para recomeçar."},
    "group_summary_title": {"zh": "📊 今日群组摘要", "en": "📊 Today's Recap", "ru": "📊 Итоги дня", "id": "📊 Rekap Hari Ini", "pt": "📊 Resumo de Hoje"},
    "group_summary_header": {"zh": "📊 <b>今日群组摘要</b>", "en": "📊 <b>Today's Recap</b>", "ru": "📊 <b>Итоги дня</b>", "id": "📊 <b>Rekap Hari Ini</b>", "pt": "📊 <b>Resumo de Hoje</b>"},
    "group_summary_swipes": {"zh": "🔄 今日刷卡: {count} 张", "en": "🔄 Stories swiped: {count}", "ru": "🔄 Просмотрено историй: {count}", "id": "🔄 Cerita digeser: {count}", "pt": "🔄 Histórias passadas: {count}"},
    "group_summary_posters": {"zh": "📝 匿名大字报: {count} 条", "en": "📝 Stories posted: {count}", "ru": "📝 Написано историй: {count}", "id": "📝 Cerita diposting: {count}", "pt": "📝 Histórias postadas: {count}"},
    "group_summary_top": {"zh": "🏆 最热卡片 ({count} 个表情):", "en": "🏆 Top story ({count} reactions):", "ru": "🏆 Топ история ({count} реакций):", "id": "🏆 Cerita terpopuler ({count} reaksi):", "pt": "🏆 Mais popular ({count} reações):"},
    "group_summary_cta": {"zh": "明天继续！发送 /world 开始刷故事 🚀", "en": "See you tomorrow! Send /world to dive in 🚀", "ru": "До завтра! Отправь /world 🚀", "id": "Sampai besok! Kirim /world buat lanjut 🚀", "pt": "Até amanhã! Envie /world pra começar 🚀"},
    "checkin_success": {"zh": "✅ 签到成功！+{points} 积分\n当前积分：{total}", "en": "✅ Checked in! +{points} pts\nTotal: {total}", "ru": "✅ Отмечено! +{points} баллов\nВсего: {total}", "id": "✅ Check-in berhasil! +{points} poin\nTotal: {total}", "pt": "✅ Check-in feito! +{points} pts\nTotal: {total}"},
    "checkin_already": {"zh": "⚠️ 今天已经签到过了，明天再来吧！", "en": "⚠️ Already checked in today — come back tomorrow!", "ru": "⚠️ Ты уже отмечался сегодня — приходи завтра!", "id": "⚠️ Udah check-in hari ini — balik lagi besok!", "pt": "⚠️ Já fez check-in hoje — volta amanhã!"},
    "milestone_10": {"zh": "🎉 你的故事引起了 10 个人的共鸣！+10 积分", "en": "🎉 10 people felt your story! +10 pts", "ru": "🎉 Твоя история зацепила 10 человек! +10 баллов", "id": "🎉 10 orang ngerasain ceritamu! +10 poin", "pt": "🎉 10 pessoas sentiram sua história! +10 pts"},
    "milestone_30": {"zh": "🔥 30 个人为你的故事留下了表情！+30 积分", "en": "🔥 30 people reacted to your story! +30 pts", "ru": "🔥 30 человек отреагировали! +30 баллов", "id": "🔥 30 orang bereaksi sama ceritamu! +30 poin", "pt": "🔥 30 pessoas reagiram! +30 pts"},
    "milestone_100": {"zh": "🔥 你的故事火了！+100 积分", "en": "🔥 Your story went viral! +100 pts", "ru": "🔥 Твоя история завирусилась! +100 баллов", "id": "🔥 Ceritamu viral! +100 poin", "pt": "🔥 Sua história viralizou! +100 pts"},
    "milestone_300": {"zh": "🏆 传奇故事！+300 积分", "en": "🏆 Legendary story! +300 pts", "ru": "🏆 Легендарная история! +300 баллов", "id": "🏆 Cerita legendaris! +300 poin", "pt": "🏆 História lendária! +300 pts"},
    "milestone_1000": {"zh": "👑 现象级创作！+1000 积分", "en": "👑 Phenomenal! +1000 pts", "ru": "👑 Феноменально! +1000 баллов", "id": "👑 Fenomenal! +1000 poin", "pt": "👑 Fenomenal! +1000 pts"},
    "invite_success": {"zh": "🎉 邀请成功！+{points} 积分", "en": "🎉 Invite landed! +{points} pts", "ru": "🎉 Приглашение принято! +{points} баллов", "id": "🎉 Undangan berhasil! +{points} poin", "pt": "🎉 Convite aceito! +{points} pts"},
    "invite_link": {"zh": "🔗 你的邀请链接：\n{link}\n\n每成功邀请一人 +50 积分！", "en": "🔗 Your invite link:\n{link}\n\n+50 pts per invite!", "ru": "🔗 Твоя ссылка:\n{link}\n\n+50 баллов за приглашение!", "id": "🔗 Link undanganmu:\n{link}\n\n+50 poin per undangan!", "pt": "🔗 Seu link de convite:\n{link}\n\n+50 pts por convite!"},
    "settings_title": {"zh": "⚙️ 设置", "en": "⚙️ Settings", "ru": "⚙️ Настройки", "id": "⚙️ Setelan", "pt": "⚙️ Configurações"},
    "settings_language": {"zh": "🌐 语言", "en": "🌐 Language", "ru": "🌐 Язык", "id": "🌐 Bahasa", "pt": "🌐 Idioma"},
    "settings_country": {"zh": "🌍 国家", "en": "🌍 Country", "ru": "🌍 Страна", "id": "🌍 Negara", "pt": "🌍 País"},
    "settings_channels": {"zh": "📺 频道订阅", "en": "📺 Channels", "ru": "📺 Каналы", "id": "📺 Channel", "pt": "📺 Canais"},
    "settings_show_country": {"zh": "📍 发帖显示位置", "en": "📍 Show location on posts", "ru": "📍 Показывать место в постах", "id": "📍 Tampilkan lokasi di postingan", "pt": "📍 Mostrar localização nos posts"},
    "lang_changed": {"zh": "✅ 语言已切换为中文", "en": "✅ Language changed to English", "ru": "✅ Язык изменён на русский", "id": "✅ Bahasa diubah ke Indonesia", "pt": "✅ Idioma alterado para Português"},
    "error_generic": {"zh": "⚠️ 出了点问题，请稍后重试", "en": "⚠️ Something went wrong — try again", "ru": "⚠️ Что-то пошло не так — попробуй ещё раз", "id": "⚠️ Ada yang salah — coba lagi ya", "pt": "⚠️ Algo deu errado — tente de novo"},
    "error_not_found": {"zh": "⚠️ 内容不存在或已下架", "en": "⚠️ This story is gone or was removed", "ru": "⚠️ Эта история удалена или не найдена", "id": "⚠️ Cerita ini udah nggak ada atau dihapus", "pt": "⚠️ Essa história sumiu ou foi removida"},
    "my_stories_title": {"zh": "📊 <b>我的故事</b>", "en": "📊 <b>My Stories</b>", "ru": "📊 <b>Мои истории</b>", "id": "📊 <b>Ceritaku</b>", "pt": "📊 <b>Minhas Histórias</b>"},
    "no_stories_yet": {"zh": "你还没有发布过故事", "en": "You haven't posted anything yet", "ru": "Ты ещё ничего не публиковал", "id": "Kamu belum pernah posting", "pt": "Você ainda não publicou nada"},
    "my_favorites_title": {"zh": "⭐ <b>我的收藏</b>", "en": "⭐ <b>Saved</b>", "ru": "⭐ <b>Сохранённое</b>", "id": "⭐ <b>Tersimpan</b>", "pt": "⭐ <b>Salvos</b>"},
    "no_favorites_yet": {"zh": "你还没有收藏过内容", "en": "Nothing saved yet", "ru": "Пока ничего не сохранено", "id": "Belum ada yang disimpan", "pt": "Nada salvo ainda"},
    "btn_my_stories": {"zh": "📊 我的故事", "en": "📊 My Stories", "ru": "📊 Мои истории", "id": "📊 Ceritaku", "pt": "📊 Histórias"},
    "btn_my_favorites": {"zh": "⭐ 我的收藏", "en": "⭐ Saved", "ru": "⭐ Сохранённое", "id": "⭐ Tersimpan", "pt": "⭐ Salvos"},
    "btn_my_team": {"zh": "👥 我的邀请团队", "en": "👥 My Invite Team", "ru": "👥 Мои приглашённые", "id": "👥 Tim Undanganku", "pt": "👥 Meu Time"},
    "team_header": {"zh": "👥 <b>我的邀请团队</b>（共 {count} 人）\n\n🔄 刷帖数 · 🏆 积分 · 🕐 最近活跃", "en": "👥 <b>My Invite Team</b> ({count} members)\n\n🔄 Swipes · 🏆 Points · 🕐 Last active", "ru": "👥 <b>Мои приглашённые</b> ({count} чел.)\n\n🔄 Свайпов · 🏆 Баллов · 🕐 Посл. активность", "id": "👥 <b>Tim Undanganku</b> ({count} orang)\n\n🔄 Geseran · 🏆 Poin · 🕐 Terakhir aktif", "pt": "👥 <b>Meu Time</b> ({count} pessoas)\n\n🔄 Swipes · 🏆 Pontos · 🕐 Último acesso"},
    "team_empty": {"zh": "还没有邀请任何人。分享你的邀请链接，每成功邀请一人可获得积分！", "en": "No invites yet. Share your link — earn points for every person you bring in!", "ru": "Ещё никого нет. Поделись ссылкой — получай баллы за каждого приглашённого!", "id": "Belum ada yang diundang. Bagikan linkmu — dapatkan poin tiap undangan!", "pt": "Nenhum convite ainda. Compartilhe seu link — ganhe pontos por cada pessoa!"},
    "team_never_active": {"zh": "未活跃", "en": "inactive", "ru": "неактивен", "id": "belum aktif", "pt": "inativo"},
    "team_footer": {"zh": "👑 = 已开通会员", "en": "👑 = Premium member", "ru": "👑 = Премиум", "id": "👑 = Member premium", "pt": "👑 = Membro premium"},
    "group_invite_onboarding": {"zh": "👥 <b>和朋友一起刷故事更有趣！</b>\n\n把 Blink.World Bot 拉进你的群，群里发 /world 就能一起刷匿名故事。\n\n👇 点击下方按钮，选择一个群添加", "en": "👥 <b>Stories hit different with friends!</b>\n\nAdd Blink.World Bot to your group chat. Send /world in the group to swipe through anonymous stories together.\n\n👇 Tap the button below to pick a group", "ru": "👥 <b>С друзьями истории заходят иначе!</b>\n\nДобавь Blink.World Bot в свою группу. Отправь /world в группе, чтобы листать анонимные истории вместе.\n\n👇 Нажми кнопку ниже", "id": "👥 <b>Baca cerita bareng temen lebih seru!</b>\n\nTambahkan Blink.World Bot ke grup kamu. Kirim /world di grup buat geser-geser cerita anonim bareng.\n\n👇 Ketuk tombol di bawah buat pilih grup", "pt": "👥 <b>Histórias são melhores em grupo!</b>\n\nAdicione o Blink.World Bot ao seu grupo. Envie /world no grupo pra ver histórias anônimas juntos.\n\n👇 Toque no botão abaixo pra escolher um grupo"},
    "group_invite_after_cards": {"zh": "想和朋友一起刷吗？👇", "en": "Wanna swipe with friends? 👇", "ru": "Хочешь листать с друзьями? 👇", "id": "Mau geser-geser bareng temen? 👇", "pt": "Quer ver com amigos? 👇"},
    "btn_add_to_group": {"zh": "👥 添加到群聊", "en": "👥 Add to Group", "ru": "👥 Добавить в группу", "id": "👥 Tambahkan ke Grup", "pt": "👥 Adicionar ao Grupo"},
    "btn_skip_group": {"zh": "⏭️ 先跳过", "en": "⏭️ Maybe later", "ru": "⏭️ Потом", "id": "⏭️ Nanti aja", "pt": "⏭️ Depois"},
    "group_invite_soft_reminder": {"zh": "💡 试试把 Bot 拉进你的群，和朋友一起刷故事吧！", "en": "💡 Add the Bot to your group — swipe stories with friends!", "ru": "💡 Добавь бота в группу — листай истории с друзьями!", "id": "💡 Tambahkan Bot ke grup — geser cerita bareng temen!", "pt": "💡 Adicione o Bot ao grupo — veja histórias com amigos!"},
    "country_input_hint": {"zh": "🌍 你在哪个国家？\n\n点击下方按钮快速选择，或者<b>直接输入你的国家名称</b>（支持任何语言）。", "en": "🌍 Where are you based?\n\nTap a button or just <b>type your country</b> in any language.", "ru": "🌍 Откуда ты?\n\nНажми кнопку или просто <b>напиши свою страну</b> на любом языке.", "id": "🌍 Kamu dari mana?\n\nKetuk tombol atau langsung <b>ketik nama negaramu</b> pakai bahasa apa aja.", "pt": "🌍 De onde você é?\n\nToque num botão ou simplesmente <b>digite seu país</b> em qualquer idioma."},
    "country_change_hint": {"zh": "🌍 选择或输入你的国家（支持任何语言）：", "en": "🌍 Pick or type your country (any language):", "ru": "🌍 Выбери или напиши страну (любой язык):", "id": "🌍 Pilih atau ketik negaramu (bahasa apa aja):", "pt": "🌍 Escolha ou digite seu país (qualquer idioma):"},
    "share_card_footer": {"zh": "\n\n🌍 更多匿名真实故事 👉 {bot_link}", "en": "\n\n🌍 More anonymous stories 👉 {bot_link}", "ru": "\n\n🌍 Ещё анонимные истории 👉 {bot_link}", "id": "\n\n🌍 Lebih banyak cerita anonim 👉 {bot_link}", "pt": "\n\n🌍 Mais histórias anônimas 👉 {bot_link}"},
}


def t(key: str, lang: str = "zh", **kwargs: Any) -> str:
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
    if not language_code:
        return "en"
    code = language_code.lower()[:2]
    mapping = {"zh": "zh", "ru": "ru", "id": "id", "in": "id", "pt": "pt", "en": "en"}
    return mapping.get(code, "en")


def guess_country(language_code: str | None) -> str:
    if not language_code:
        return ""
    code = language_code.lower()[:2]
    mapping = {"zh": "中国", "ru": "俄罗斯", "id": "印尼", "in": "印尼", "pt": "巴西", "en": "United States", "ja": "日本", "ko": "韩国", "es": "西班牙", "fr": "法国", "de": "德国", "ar": "沙特阿拉伯", "hi": "印度"}
    return mapping.get(code, "")


# Maps country name (stored as Chinese) → bot language code.
# Only covers languages the bot actually supports; everything else falls back to "en".
_COUNTRY_LANG: dict[str, str] = {
    # Chinese
    "中国": "zh",
    "台湾": "zh",
    "香港": "zh",
    "澳门": "zh",
    # Russian
    "俄罗斯": "ru",
    # Indonesian / Malay (id covers both well enough)
    "印尼": "id",
    "印度尼西亚": "id",
    "马来西亚": "id",
    # Portuguese
    "巴西": "pt",
    "葡萄牙": "pt",
}


def country_to_lang(country_zh: str) -> str | None:
    """
    Return the preferred bot language for a given country (stored as Chinese name).
    Returns None if no specific mapping exists (caller should keep existing lang).
    """
    return _COUNTRY_LANG.get(country_zh)
