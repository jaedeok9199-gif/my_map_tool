import streamlit as st
import requests
import folium
import pandas as pd
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 및 모던 UI 설정
# ==========================================
st.set_page_config(page_title="신규 업체 입점 검토 시스템", page_icon="📍", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F9FAFB; font-family: 'Pretendard', sans-serif; }
    #MainMenu, header, footer {visibility: hidden;}
    h1 { font-weight: 800; color: #111827; letter-spacing: -0.5px; margin-bottom: 0rem; }
    .st-emotion-cache-16idsys p { color: #6B7280; font-size: 1.1rem; margin-top: 0.5rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; background-color: #2563EB; color: white; border: none; padding: 0.6rem 1rem; transition: all 0.2s; }
    .stButton>button:hover { background-color: #1D4ED8; transform: translateY(-1px); }
    .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #D1D5DB; padding: 0.6rem; }
</style>
""", unsafe_allow_html=True)

def get_clean_pin(color_hex, is_search=False):
    w, h = (20, 28) if is_search else (12, 18)
    return f'''
    <div class="custom-pin-icon" style="transition: transform 0.15s ease-out; transform-origin: bottom center;">
        <svg width="{w}" height="{h}" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 34 12 34C12 34 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="{color_hex}"/>
        </svg>
    </div>
    '''

# ==========================================
# 2. 시공점 데이터 로드 (가볍고 빠르게!)
# ==========================================
@st.cache_data
def load_stores():
    df = pd.DataFrame()
    for enc in ['utf-8', 'euc-kr', 'cp949', 'latin-1', 'utf-8-sig']:
        try:
            df = pd.read_csv('시공점.csv', encoding=enc)
            if not df.empty: break
        except: continue
        
    if df.empty:
        for enc in ['utf-8', 'euc-kr', 'cp949']:
            try:
                df = pd.read_csv('stores.csv', encoding=enc)
                if not df.empty: break
            except: continue

    if not df.empty:
        col_map = {'업체코드':'code', '업체명':'name', '위도':'lat', '경도':'lng', '월평균 예약 수':'avg_monthly_reservations', '월평균예약수':'avg_monthly_reservations', '재구매율':'repurchase_rate'}
        df = df.rename(columns=col_map)
        df['lat'] = pd.to_numeric(df.get('lat', []), errors='coerce')
        df['lng'] = pd.to_numeric(df.get('lng', []), errors='coerce')
        df = df.dropna(subset=['lat', 'lng']).reset_index(drop=True)
        
        # 팝업에 띄울 핵심 데이터 정리
        df['code'] = df.get('code', '없음').fillna('없음').astype(str)
        df['name'] = df.get('name', '없음').fillna('없음').astype(str)
        df['avg_monthly_reservations'] = pd.to_numeric(df.get('avg_monthly_reservations', 0).astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0)
        df['repurchase_rate'] = pd.to_numeric(df.get('repurchase_rate', 0).astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0)
    
    return df

stores_df = load_stores()

# ==========================================
# 3. 앱 UI 및 사이드바 설정
# ==========================================
st.title("정비소 공급망 지도")
st.caption("신규 주소를 검색하고 기존 매장과의 커버리지 및 상권을 비교하세요.")

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    user_kakao_key = st.text_input("카카오 REST API 키", value="", type="password")
    st.markdown("---")
    st.markdown("**🔴 신규 입점 검토 반경**")
    radius_km = st.slider("반경 범위 (km)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
    st.success(f"✅ 연동된 기존 시공점: {len(stores_df)}개")

def get_kakao_coords(address, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    for search_type in ['address', 'keyword']:
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/{search_type}.json?query={address}", headers=headers)
        if res.status_code == 200 and res.json()['documents']:
            doc = res.json()['documents'][0]
            return float(doc['y']), float(doc['x']), doc.get('address_name', doc.get('place_name', address))
    return None, None, None

search_col1, search_col2 = st.columns([3, 1])
with search_col1: address = st.text_input("신규 검토 주소 입력", placeholder="예: 성남시 중원구 희망로 415", label_visibility="collapsed")
with search_col2: search_clicked = st.button("입점 상권 검토")

search_lat, search_lng, found_name = None, None, None

if search_clicked:
    if not user_kakao_key: st.error("사이드바에 카카오 API 키를 입력해주세요.")
    elif address.strip():
        with st.spinner("위치 데이터 분석 중..."):
            search_lat, search_lng, found_name = get_kakao_coords(address, user_kakao_key)
            if search_lat and search_lng:
                st.success(f"📍 '{found_name}' 위치 탐색 성공")
                c1, c2 = st.columns(2)
                with c1: st.markdown("**위도**"); st.code(f"{search_lat:.6f}", language="text")
                with c2: st.markdown("**경도**"); st.code(f"{search_lng:.6f}", language="text")
            else: st.error("주소를 찾을 수 없습니다.")

# ==========================================
# 4. 지도 생성 및 레이어 병합
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)

center_lat = search_lat if search_lat else (stores_df['lat'].mean() if not stores_df.empty else 37.5665)
center_lng = search_lng if search_lng else (stores_df['lng'].mean() if not stores_df.empty else 126.9780)
zoom_level = 14 if search_lat and radius_km <= 2 else (13 if search_lat and radius_km <= 5 else 11)

m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level, tiles='OpenStreetMap')

# 커버리지 반경 원 (우측 상단 레이어 컨트롤에서 켜고 끄기 가능)
radii = [3, 5, 10, 15]
for r_km in radii:
    is_default = (r_km == 5) # 기본적으로 5km만 켜둠
    radius_layer = folium.FeatureGroup(name=f'🎯 기존 시공점 커버리지 ({r_km}km)', show=is_default)
    for _, row in stores_df.iterrows():
        folium.Circle(
            location=[row['lat'], row['lng']], radius=r_km * 1000,
            color='#0288D1', fill=True, 
            fillColor='#B3E5FC', fillOpacity=0.1, weight=1
        ).add_to(radius_layer)
    radius_layer.add_to(m)

# 📍 [업체 마커 레이어] - 팝업 카드 적용
shop_layer = folium.FeatureGroup(name=f'📍 전체 매장 마커', show=True)
for _, row in stores_df.iterrows():
    popup_html = f"""
    <div style="font-family:'Pretendard', sans-serif; min-width:190px; padding: 4px;">
        <h4 style="margin:0 0 8px 0; color:#1E3A8A; font-size:14px; font-weight:700; border-bottom:2px solid #38BDF8; padding-bottom:5px;">
            📍 {row['name']}
        </h4>
        <div style="font-size:12px; color:#374151; line-height:1.6;">
            <p style="margin:3px 0;"><b>• 업체코드:</b> <span style="color:#111827;">{row['code']}</span></p>
            <p style="margin:3px 0;"><b>• 업체명:</b> <span style="color:#111827;">{row['name']}</span></p>
            <p style="margin:3px 0;"><b>• 월평균 예약 수:</b> <span style="color:#2563EB; font-weight:600;">{row['avg_monthly_reservations']:,.0f}건</span></p>
            <p style="margin:3px 0;"><b>• 재구매율:</b> <span style="color:#059669; font-weight:600;">{row['repurchase_rate']:.1f}%</span></p>
        </div>
    </div>
    """
    
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"{row['name']} ({row['code']})",
        icon=folium.DivIcon(
            html=get_clean_pin('#38BDF8', is_search=False),
            icon_size=(12, 18),
            icon_anchor=(6, 18)
        )
    ).add_to(shop_layer)
shop_layer.add_to(m)

# 검색 위치 마커
if search_lat and search_lng:
    search_layer = folium.FeatureGroup(name=f'🚨 신규 입점 검토 위치', show=True)
    folium.Circle(
        location=[search_lat, search_lng], radius=radius_km * 1000,
        color='#DC2626', fill=True, fillColor='#EF4444', fillOpacity=0.2, weight=2.5
    ).add_to(search_layer)

    svg_pin = get_clean_pin('#DC2626', is_search=True)
    folium.Marker(
        location=[search_lat, search_lng], popup=f"<b>신규 검토 위치</b><br>{address}", tooltip=f"검토 반경: {radius_km}km",
        icon=folium.DivIcon(html=svg_pin, icon_size=(20, 28), icon_anchor=(10, 28))
    ).add_to(search_layer)
    search_layer.add_to(m)

folium.LayerControl(collapsed=False, position='topright').add_to(m)

zoom_script = """
<script>
document.addEventListener("DOMContentLoaded", function() { setTimeout(function() {
    var map_keys = Object.keys(window).filter(k => k.startsWith('map_'));
    if (map_keys.length > 0) {
        var myMap = window[map_keys[0]];
        function adjustMarkerScale() {
            var zoom = myMap.getZoom();
            var scale = Math.max(0.4, Math.min(3.0, 1.0 + (zoom - 11) * 0.25));
            document.querySelectorAll('.custom-pin-icon').forEach(p => p.style.transform = 'scale(' + scale + ')');
        }
        myMap.on('zoomend', adjustMarkerScale); adjustMarkerScale();
    }
}, 500);});
</script>
"""
m.get_root().html.add_child(folium.Element(zoom_script))

components.html(m.get_root().render(), height=650)
