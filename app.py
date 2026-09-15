import streamlit as st
import requests
import folium
import pandas as pd
import streamlit.components.v1 as components

# 페이지 기본 설정 (가장 먼저 호출되어야 함)
st.set_page_config(page_title="위치 비교 툴", page_icon="📍", layout="wide")

# ==========================================
# 🎨 [디자인 커스텀 CSS 주입] - 담백하고 모던한 스타일
# ==========================================
st.markdown("""
<style>
    /* 전체 배경색 및 폰트 변경 (Pretendard 등 모던 폰트 적용) */
    .stApp {
        background-color: #F9FAFB;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* 우측 상단 기본 메뉴 및 하단 워터마크 숨김 */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 제목 스타일링 */
    h1 {
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.5px;
        margin-bottom: 0rem;
    }
    
    /* 부제목(캡션) 스타일링 */
    .st-emotion-cache-16idsys p {
        color: #6B7280;
        font-size: 1.1rem;
        margin-top: 0.5rem;
    }
    
    /* 버튼 모던화 */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        background-color: #2563EB;
        color: white;
        border: none;
        padding: 0.6rem 1rem;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transform: translateY(-1px);
    }
    
    /* 입력창 모던화 */
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #D1D5DB;
        padding: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

st.title("📍 매장 위치 탐색기")
st.caption("주소를 검색하고 주변 매장과의 거리를 한눈에 비교하세요.")

# ------------------------------------------------------------------
# [카카오 REST API 키 설정]
DEFAULT_KAKAO_KEY = "" 
# ------------------------------------------------------------------

# 사이드바 설정 영역
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    user_kakao_key = st.text_input("카카오 REST API 키", value=DEFAULT_KAKAO_KEY, type="password")
    st.markdown("---")
    radius_km = st.slider("🔴 반경 범위 (km)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)

def get_clean_pin(color_hex, is_search=False):
    w, h = (20, 28) if is_search else (12, 18)
    svg = f'''
    <div class="custom-pin-icon" style="transition: transform 0.15s ease-out; transform-origin: bottom center;">
        <svg width="{w}" height="{h}" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 34 12 34C12 34 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="{color_hex}"/>
        </svg>
    </div>
    '''
    return svg

@st.cache_data
def load_stores():
    try:
        df = pd.read_csv('stores.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('stores.csv', encoding='cp949')
        
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lng'] = pd.to_numeric(df['lng'], errors='coerce')
    return df.dropna(subset=['lat', 'lng'])

try:
    stores_df = load_stores()
    st.sidebar.success(f"✅ 연동된 매장: {len(stores_df)}개")
except Exception as e:
    st.sidebar.error("데이터를 불러올 수 없습니다.")
    stores_df = pd.DataFrame(columns=['name', 'lat', 'lng'])

def get_kakao_coords(address, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    url_addr = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    res = requests.get(url_addr, headers=headers)
    if res.status_code == 200 and res.json()['documents']:
        doc = res.json()['documents'][0]
        return float(doc['y']), float(doc['x']), doc.get('address_name', address)
        
    url_kw = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={address}"
    res_kw = requests.get(url_kw, headers=headers)
    if res_kw.status_code == 200 and res_kw.json()['documents']:
        doc = res_kw.json()['documents'][0]
        return float(doc['y']), float(doc['x']), doc.get('place_name', address)
        
    return None, None, None

# 레이아웃 분리: 검색창과 버튼을 한 줄에 깔끔하게 배치
search_col1, search_col2 = st.columns([3, 1])
with search_col1:
    address = st.text_input("검색할 주소를 입력하세요", placeholder="예: 성남시 중원구 희망로 415", label_visibility="collapsed")
with search_col2:
    search_clicked = st.button("위치 탐색")

search_lat, search_lng, found_name = None, None, None

if search_clicked:
    if not user_kakao_key:
        st.error("사이드바에 카카오 API 키를 입력해주세요.")
    elif address.strip():
        with st.spinner("위치 데이터를 분석 중입니다..."):
            search_lat, search_lng, found_name = get_kakao_coords(address, user_kakao_key)
            
            if search_lat and search_lng:
                st.success(f"📍 '{found_name}' 위치를 찾았습니다.")
                
                # [클릭 복사 기능 적용 구역] - 코드를 담백하게 표시하고 우측 상단 복사 아이콘 제공
                coord_col1, coord_col2 = st.columns(2)
                with coord_col1:
                    st.markdown("**위도 (Latitude)**")
                    st.code(f"{search_lat:.6f}", language="text")
                with coord_col2:
                    st.markdown("**경도 (Longitude)**")
                    st.code(f"{search_lng:.6f}", language="text")
            else:
                st.error("주소를 찾을 수 없습니다. 다시 확인해 주세요.")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(f"**🗺️ 위치 지도** (🔴 검색 위치 반경 {radius_km}km / 🔵 기존 매장)")

if search_lat and search_lng:
    center_lat, center_lng = search_lat, search_lng
    zoom_level = 14 if radius_km <= 2 else (13 if radius_km <= 5 else 12)
elif not stores_df.empty:
    center_lat, center_lng, zoom_level = stores_df['lat'].mean(), stores_df['lng'].mean(), 11
else:
    center_lat, center_lng, zoom_level = 37.5665, 126.9780, 11

m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)

for _, row in stores_df.iterrows():
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=f"<b>{row['name']}</b>",
        tooltip=f"{row['name']}",
        icon=folium.DivIcon(
            html=get_clean_pin('#38BDF8', is_search=False),
            icon_size=(12, 18),
            icon_anchor=(6, 18)
        )
    ).add_to(m)

if search_lat and search_lng:
    folium.Circle(
        location=[search_lat, search_lng],
        radius=radius_km * 1000,
        color='#F87171',
        fill=True,
        fill_color='#F87171',
        fill_opacity=0.15,
        weight=1.5
    ).add_to(m)

    folium.Marker(
        location=[search_lat, search_lng],
        popup=f"<b>검색 위치</b><br>{address}",
        tooltip=f"{address}",
        icon=folium.DivIcon(
            html=get_clean_pin('#F87171', is_search=True),
            icon_size=(20, 28),
            icon_anchor=(10, 28)
        )
    ).add_to(m)

zoom_script = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(function() {
        var map_keys = Object.keys(window).filter(k => k.startsWith('map_'));
        if (map_keys.length > 0) {
            var myMap = window[map_keys[0]];
            
            function adjustMarkerScale() {
                var zoom = myMap.getZoom();
                var scale = Math.max(0.4, Math.min(3.0, 1.0 + (zoom - 11) * 0.25));
                var pins = document.querySelectorAll('.custom-pin-icon');
                pins.forEach(function(pin) {
                    pin.style.transform = 'scale(' + scale + ')';
                });
            }
            
            myMap.on('zoomend', adjustMarkerScale);
            adjustMarkerScale();
        }
    }, 500);
});
</script>
"""
m.get_root().html.add_child(folium.Element(zoom_script))

# 지도를 카드 형태의 그림자 안에 넣어 모던하게 연출
components.html(m.get_root().render(), height=600)
