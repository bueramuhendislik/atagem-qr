import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO
import time
from datetime import datetime
import uuid
import json
import os
import base64

# --- LOGOLAR ---
# logos.py dosyasından yükle (aynı klasörde olmalı)
try:
    from logos import ATAGEM_B64, BUERA_B64
except ImportError:
    ATAGEM_B64 = ""
    BUERA_B64 = ""

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ATA-GEM Kayıt Sistemi", page_icon="⚙️", layout="centered")

# --- CONFIG ---
def load_config():
    default = {
        "etkinlik_adi": "Etkinlik Adını Buraya Yaz",
        "kulup_adi": "ATA-GEM",
    }
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        default.update(cfg)
    return default

def save_config(cfg):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)

cfg = load_config()

# --- GLOBAL CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp { background: #080C1A; color: #F0F0F5; }

.stButton > button {
    background: linear-gradient(135deg, #1B2A6B, #2D4AB0) !important;
    color: white !important; border: none !important;
    border-radius: 12px !important; padding: 0.65rem 1.5rem !important;
    font-family: 'DM Sans', sans-serif !important; font-weight: 600 !important;
    font-size: 1rem !important; transition: all 0.2s ease !important;
    box-shadow: 0 4px 20px rgba(27,42,107,0.4) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(27,42,107,0.6) !important;
}

.stTextInput > div > div > input {
    background: #0F1525 !important; border: 1px solid #1E2A45 !important;
    border-radius: 10px !important; color: #F0F0F5 !important;
}
.stTextInput > div > div > input:focus {
    border-color: #2D4AB0 !important;
    box-shadow: 0 0 0 3px rgba(45,74,176,0.25) !important;
}
div[data-baseweb="select"] > div {
    background: #0F1525 !important; border: 1px solid #1E2A45 !important;
    border-radius: 10px !important; color: #F0F0F5 !important;
}
label {
    color: #8A9ABF !important; font-size: 0.82rem !important;
    font-weight: 600 !important; letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, #1B2A6B, #4A6AE0) !important;
    border-radius: 99px !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: #0F1525 !important; border-radius: 12px !important;
    padding: 4px !important; gap: 4px !important;
}
.stTabs [data-baseweb="tab"] { border-radius: 8px !important; color: #8A9ABF !important; }
.stTabs [aria-selected="true"] { background: #1B2A6B !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- TOKEN MANAGER ---
@st.cache_resource
class TokenManager:
    def __init__(self):
        self.active_gate_tokens = {}

    def create_token(self, lifespan_seconds=15):
        now = time.time()
        self.active_gate_tokens = {k: v for k, v in self.active_gate_tokens.items() if v > now}
        token = str(uuid.uuid4())
        self.active_gate_tokens[token] = now + lifespan_seconds + 30
        return token

    def is_valid(self, token):
        now = time.time()
        return token in self.active_gate_tokens and self.active_gate_tokens[token] > now

manager = TokenManager()

# --- VERİTABANI ---
def init_db():
    conn = sqlite3.connect('katilimcilar.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS katilimcilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT NOT NULL,
            soyisim TEXT NOT NULL,
            bolum TEXT,
            sinif TEXT,
            mail TEXT,
            kayit_zamani TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(isim, soyisim, bolum, sinif, mail):
    conn = sqlite3.connect('katilimcilar.db')
    c = conn.cursor()
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO katilimcilar (isim, soyisim, bolum, sinif, mail, kayit_zamani) VALUES (?,?,?,?,?,?)",
        (isim, soyisim, bolum, sinif, mail, zaman)
    )
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect('katilimcilar.db')
    df = pd.read_sql_query("SELECT * FROM katilimcilar ORDER BY id DESC", conn)
    conn.close()
    return df

init_db()

# --- LOGO HTML YARDIMCILARI ---
def atagem_logo_html(size=80, border_radius=16):
    return (
        '<img src="data:image/jpeg;base64,' + ATAGEM_B64 + '" '
        'style="width:' + str(size) + 'px;height:' + str(size) + 'px;object-fit:contain;'
        'border-radius:' + str(border_radius) + 'px;'
        'background:white;padding:6px;box-shadow:0 4px 20px rgba(27,42,107,0.3);">'
    )

def buera_logo_html(size=44):
    return (
        '<img src="data:image/png;base64,' + BUERA_B64 + '" '
        'style="width:' + str(size) + 'px;height:' + str(size) + 'px;object-fit:contain;'
        'border-radius:8px;opacity:0.85;">'
    )

# --- MOD ---
query_params = st.query_params
mod = query_params.get("mod", "admin")

# ============================================================
# 1. KAYIT FORMU
# ============================================================
if mod == "kayit":
    token = query_params.get("token", None)

    st.markdown(
        '<div style="text-align:center; padding: 2rem 0 1.5rem;">'
        '<div style="display:flex;justify-content:center;margin-bottom:1.2rem;">'
        + atagem_logo_html(80) +
        '</div>'
        '<p style="font-family:\'Space Grotesk\',sans-serif;font-size:0.7rem;font-weight:700;'
        'letter-spacing:0.18em;color:#4A6AE0;text-transform:uppercase;margin:0 0 0.4rem;">'
        + cfg['kulup_adi'] +
        '</p>'
        '<h1 style="font-family:\'Space Grotesk\',sans-serif;font-size:1.7rem;font-weight:700;'
        'color:#F0F0F5;margin:0 0 0.4rem;line-height:1.2;">'
        + cfg['etkinlik_adi'] +
        '</h1>'
        '<p style="color:#4A5A80;font-size:0.88rem;margin:0;">Formu doldurarak etkinliğe kaydolun</p>'
        '</div>',
        unsafe_allow_html=True
    )

    if st.session_state.get("form_unlocked", False) or (token and manager.is_valid(token)):
        st.session_state["form_unlocked"] = True

        if st.session_state.get("kayit_tamam", False):
            isim_k = st.session_state.get("son_isim", "")
            st.markdown(
                '<div style="background:linear-gradient(135deg,#0D1F12,#0A1A10);'
                'border:1px solid #1E3A25;border-radius:16px;'
                'padding:2.5rem;text-align:center;margin:1rem 0;">'
                '<div style="font-size:3rem;margin-bottom:0.8rem;">🎉</div>'
                '<h2 style="color:#4ADE80;font-family:\'Space Grotesk\',sans-serif;margin:0 0 0.4rem;">'
                'Kaydınız Alındı!</h2>'
                '<p style="color:#6AAA80;margin:0;">Teşekkürler ' + isim_k + ', görüşmek üzere!</p>'
                '</div>',
                unsafe_allow_html=True
            )
            
        else:
            with st.form("kayit_formu", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    isim = st.text_input("İsim *")
                with col2:
                    soyisim = st.text_input("Soyisim *")

                bolum = st.text_input("Bölüm *", placeholder="örn. Bilgisayar Mühendisliği")

                col3, col4 = st.columns(2)
                with col3:
                    sinif = st.selectbox("Sınıf *", [
                        "1. Sınıf", "2. Sınıf", "3. Sınıf", "4. Sınıf",
                        "Yüksek Lisans", "Doktora"
                    ])
                with col4:
                    mail = st.text_input("E-posta *", placeholder="ad@universite.edu.tr")

                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("✓  Kaydı Tamamla", use_container_width=True)

                if submitted:
                    if isim and soyisim and bolum and mail:
                        add_user(isim, soyisim, bolum, sinif, mail)
                        st.session_state["kayit_tamam"] = True
                        st.session_state["son_isim"] = isim
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("Lütfen tüm zorunlu alanları doldurun.")

            # Powered by BUERA
            st.markdown(
                '<div style="text-align:center;margin-top:1.5rem;display:flex;'
                'align-items:center;justify-content:center;gap:0.5rem;opacity:0.45;">'
                '<span style="color:#6A7A9A;font-size:0.7rem;letter-spacing:0.1em;'
                'text-transform:uppercase;font-weight:600;">Powered by</span>'
                + buera_logo_html(36) +
                '</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            '<div style="background:#150D1A;border:1px solid #3A2040;border-radius:16px;'
            'padding:2.5rem;text-align:center;margin:2rem 0;">'
            '<div style="font-size:2.5rem;margin-bottom:0.8rem;">⚠️</div>'
            '<h3 style="color:#F87171;font-family:\'Space Grotesk\',sans-serif;margin:0 0 0.4rem;">'
            'QR Kod Geçersiz</h3>'
            '<p style="color:#8A5060;margin:0;">Bu QR kodun süresi dolmuş.<br>'
            'Lütfen kapıdaki ekrandan güncel kodu okutun.</p>'
            '</div>',
            unsafe_allow_html=True
        )

# ============================================================
# 2. QR EKRANI (TABLET)
# ============================================================
elif mod == "ekran":
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        .block-container {padding-top: 0.5rem; padding-bottom: 0.5rem;}
    </style>
    """, unsafe_allow_html=True)

    base_url = query_params.get("url", "https://atagem-etkinlik.streamlit.app")
    LIFESPAN = 15

    current_token = manager.create_token(LIFESPAN)
    link = base_url + "/?mod=kayit&token=" + current_token

    # QR oluştur
    qr = qrcode.QRCode(
        box_size=12, border=3,
        error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F1525", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    qr_b64_img = base64.b64encode(buf.read()).decode()

    # Başlık
    st.markdown(
        '<div style="text-align:center; padding: 1.2rem 1rem 0.8rem;">'
        '<p style="font-family:\'Space Grotesk\',sans-serif;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.2em;color:#4A6AE0;text-transform:uppercase;margin:0 0 0.5rem;">'
        + cfg['kulup_adi'] +
        '</p>'
        '<h1 style="font-family:\'Space Grotesk\',sans-serif;'
        'font-size:clamp(1.3rem, 4vw, 2rem);font-weight:700;color:#F0F0F5;'
        'margin:0 0 0.5rem;line-height:1.2;">'
        + cfg['etkinlik_adi'] +
        '</h1>'
        '<div style="width:50px;height:3px;'
        'background:linear-gradient(90deg,#1B2A6B,#4A6AE0);'
        'border-radius:99px;margin:0 auto;"></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # QR Kart + Logolar
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'margin:0.3rem auto;max-width:400px;">'

        # QR Kart
        '<div style="background:white;border-radius:24px;padding:1.4rem;'
        'box-shadow:0 0 80px rgba(27,42,107,0.4),0 0 160px rgba(27,42,107,0.15);'
        'position:relative;">'
        '<div style="position:absolute;top:0;left:0;right:0;bottom:0;border-radius:24px;'
        'border:2px solid rgba(45,74,176,0.2);pointer-events:none;"></div>'
        '<img src="data:image/png;base64,' + qr_b64_img + '" '
        'style="width:260px;height:260px;display:block;"/>'
        '</div>'

        # ATA-GEM logosu
        '<div style="margin-top:1.4rem;display:flex;align-items:center;gap:0.9rem;'
        'background:#0F1525;border:1px solid #1E2A45;border-radius:16px;'
        'padding:0.85rem 1.5rem;">'
        + atagem_logo_html(60, 10) +
        '<div>'
        '<p style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;'
        'font-size:1.05rem;color:#F0F0F5;margin:0;letter-spacing:0.04em;">ATA-GEM</p>'
        '<p style="font-size:0.62rem;color:#4A6AE0;margin:0;'
        'letter-spacing:0.08em;text-transform:uppercase;">'
        'Ata Genç Endüstri Mühendisleri Kulübü</p>'
        '</div>'
        '</div>'

        # Powered by BUERA
        '<div style="margin-top:0.8rem;display:flex;align-items:center;'
        'gap:0.5rem;opacity:0.5;">'
        '<span style="color:#5A6A8A;font-size:0.62rem;letter-spacing:0.12em;'
        'text-transform:uppercase;font-weight:600;">Powered by</span>'
        + buera_logo_html(38) +
        '</div>'

        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div style="text-align:center;margin-top:0.8rem;">'
        '<p style="color:#4A5A80;font-size:0.82rem;margin:0;">'
        '📱 QR kodu telefonunuzla okutun ve formu doldurun'
        '</p></div>',
        unsafe_allow_html=True
    )

    status_ph = st.empty()
    bar_ph = st.progress(0)

    for i in range(LIFESPAN):
        kalan = LIFESPAN - i
        status_ph.markdown(
            '<p style="text-align:center;color:#3A4A60;font-size:0.75rem;margin:0.3rem 0 0;">'
            'QR kod <span style="color:#4A6AE0;font-weight:600;">' + str(kalan) + '</span>'
            ' saniye sonra yenileniyor</p>',
            unsafe_allow_html=True
        )
        bar_ph.progress((i + 1) / LIFESPAN)
        time.sleep(1)

    st.rerun()

# ============================================================
# 3. ADMİN PANELİ
# ============================================================
else:
    st.markdown(
        '<div style="padding:1.5rem 0 1rem;display:flex;align-items:center;gap:1rem;">'
        + atagem_logo_html(56, 12) +
        '<div>'
        '<p style="font-family:\'Space Grotesk\',sans-serif;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.15em;color:#4A6AE0;text-transform:uppercase;margin:0 0 0.2rem;">'
        + cfg['kulup_adi'] +
        '</p>'
        '<h1 style="font-family:\'Space Grotesk\',sans-serif;font-size:1.6rem;'
        'font-weight:700;color:#F0F0F5;margin:0;">Etkinlik Kontrol Merkezi</h1>'
        '</div></div>',
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["📊 Katılımcılar", "⚙️ Ayarlar", "🖥️ Ekran Linki"])

    with tab1:
        df = get_data()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Toplam Katılımcı", len(df))
        with col2:
            bugun = (
                df[df['kayit_zamani'].str.startswith(datetime.now().strftime("%Y-%m-%d"))]
                if not df.empty else pd.DataFrame()
            )
            st.metric("Bugün", len(bugun))
        with col3:
            bolum_sayisi = df['bolum'].nunique() if not df.empty else 0
            st.metric("Farklı Bölüm", bolum_sayisi)

        col_r, col_d = st.columns([1, 4])
        with col_r:
            if st.button("🔄 Yenile"):
                st.rerun()
        with col_d:
            if not df.empty:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    "📥 Excel İndir",
                    data=output.getvalue(),
                    file_name="katilimcilar.xlsx"
                )

        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                '<div style="text-align:center;padding:3rem;color:#3A4A60;">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">📭</div>'
                '<p>Henüz kayıt yok</p></div>',
                unsafe_allow_html=True
            )

        with st.expander("⚠️ Veritabanını Sıfırla"):
            st.warning("Bu işlem geri alınamaz!")
            if st.button("TÜM KAYITLARI SİL", type="primary"):
                conn = sqlite3.connect('katilimcilar.db')
                conn.execute("DELETE FROM katilimcilar")
                conn.commit()
                conn.close()
                st.success("Silindi.")
                time.sleep(1)
                st.rerun()

    with tab2:
        st.markdown("### Etkinlik Ayarları")
        new_etkinlik = st.text_input("Etkinlik Adı", value=cfg.get("etkinlik_adi", ""))
        new_kulup = st.text_input("Kulüp Adı", value=cfg.get("kulup_adi", "ATA-GEM"))
        if st.button("💾 Kaydet"):
            cfg["etkinlik_adi"] = new_etkinlik
            cfg["kulup_adi"] = new_kulup
            save_config(cfg)
            st.success("Kaydedildi!")

    with tab3:
        if "base_link" not in st.session_state:
            st.session_state["base_link"] = "https://atagem-etkinlik.streamlit.app"
        deployed_url = st.text_input("Canlı Site URL:", value=st.session_state["base_link"])
        st.session_state["base_link"] = deployed_url
        ekran_link = deployed_url + "/?mod=ekran&url=" + deployed_url
        st.markdown("**Kapı Ekranı Linki:**")
        st.code(ekran_link)
        st.link_button("🖥️ Kapı Ekranını Aç", ekran_link, use_container_width=True)
