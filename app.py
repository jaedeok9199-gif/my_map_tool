import streamlit as st
import requests
import folium
import pandas as pd
import streamlit.components.v1 as components
from folium.plugins import MarkerCluster

st.set_page_config(page_title="주소 변환 및 위치 비교 툴", page_icon="📍", layout="wide")

st.title("📍 주소 변환 및 매장 위치 비교")
st.caption("카카오 API를 연동하여 정교한 건물 위치를 탐색하고 설정한 반경 범위 내 기존 매장과 비교합니다.")

# ------------------------------------------------------------------
# [카카오 REST API 키 설정]
DEFAULT_KAKAO_KEY = "" 
# ------------------------------------------------------------------

# 사이드바 설정 영역
with st.sidebar:
    st.header("⚙️ 설정")
    user_kakao_key = st.text_input("카카오 REST API 키", value=DEFAULT_KAKAO_KEY, type="password")
    st.write("---")
    radius_km = st.slider("🔴 검색 위치 반경 설정 (km)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)

# 띠/문양 없는 완전한 깔끔 단색 SVG 핀 생성 함수
def get_clean_pin(color_hex):
    svg = f'''
    <svg width="28" height="40" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 34 12 34C12 34 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="{color_hex}"/>
    </svg>
    '''
    return svg

# CSV 파일 로드
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
    st.sidebar.success(f"불러온 매장 수: {len(stores_df)}개")
except Exception as e:
    st.error(f"stores.csv 읽기 실패: {e}")
    stores_df = pd.DataFrame(columns=['name', 'lat', 'lng'])

# 카카오 지오코딩 함수
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

address = st.text_input("검색할 주소를 입력하세요", placeholder="예: 성남시 중원구 희망로 415")
search_clicked = st.button("좌표 추출 및 위치 비교", type="primary")

search_lat, search_lng, found_name = None, None, None

if search_clicked:
    if not user_kakao_key:
        st.error("사이드바에 '카카오 REST API 키'를 입력해주세요!")
    elif address.strip():
        with st.spinner("카카오 위성 데이터 기반 정확한 좌표 탐색 중..."):
            search_lat, search_lng, found_name = get_kakao_coords(address, user_kakao_key)
            
            if search_lat and search_lng:
                st.success(f"변환 성공! [{found_name}]")
                col1, col2 = st.columns(2)
                col1.metric("위도 (Latitude)", f"{search_lat:.6f}")
                col2.metric("경도 (Longitude)", f"{search_lng:.6f}")
            else:
                st.error("주소를 찾을 수 없습니다.")

st.write("---")
st.subheader(f"🗺️ 위치 비교 지도 (🔴 검색 위치 반경 {radius_km}km / 🔵 기존 매장)")

if search_lat and search_lng:
    center_lat, center_lng = search_lat, search_lng
    zoom_level = 14 if radius_km <= 2 else (13 if radius_km <= 5 else 12)
elif not stores_df.empty:
    center_lat, center_lng, zoom_level = stores_df['lat'].mean(), stores_df['lng'].mean(), 11
else:
    center_lat, center_lng, zoom_level = 37.5665, 126.9780, 11

m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)

# 1. 기존 매장 마커 (띠 없는 깔끔한 하늘색 핀: #38BDF8)
marker_cluster = MarkerCluster().add_to(m)
for _, row in stores_df.iterrows():
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=f"<b>{row['name']}</b>",
        tooltip=f"기존 매장: {row['name']}",
        icon=folium.DivIcon(
            html=get_clean_pin('#38BDF8'), # 하늘색
            icon_size=(28, 40),
            icon_anchor=(14, 40)
        )
    ).add_to(marker_cluster)

# 2. 검색 위치 마커 (띠 없는 깔끔한 연한 붉은색 핀: #F87171) + 반경 원
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
        popup=f"<b>[검색 위치]</b><br>{address}",
        tooltip=f"검색 위치: {address}",
        icon=folium.DivIcon(
            html=get_clean_pin('#F87171'), # 연한 붉은색
            icon_size=(32, 44),
            icon_anchor=(16, 44)
        )
    ).add_to(m)

components.html(m._repr_html_(), height=580)