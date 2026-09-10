import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 데이터를 이용합니다.")


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 스트림릿 클라우드 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 사용합니다.

KOREA_TZ = ZoneInfo("Asia/Seoul")

today_korea = datetime.now(KOREA_TZ).date()
yesterday = today_korea - timedelta(days=1)

# KOBIS API에서 사용하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# 3. KOBIS API에서 데이터 가져오기
# ---------------------------------------------------------
# 같은 날짜의 데이터를 다시 요청하면 1시간 동안 캐시된 결과를 사용합니다.
# 따라서 API를 계속 반복해서 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # API 요청
    response = requests.get(url, params=params, timeout=10)

    # HTTP 오류가 발생하면 예외 발생
    response.raise_for_status()

    # JSON 데이터로 변환
    data = response.json()

    return data


# ---------------------------------------------------------
# 4. Secrets에서 인증키 가져오기
# ---------------------------------------------------------
# 스트림릿 클라우드의 Secrets에 다음과 같이 저장해야 합니다.
#
# KOBIS_KEY = "발급받은_인증키"
#
# 실제 인증키는 코드에 절대로 적지 않습니다.

try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 KOBIS_KEY를 찾을 수 없습니다.")
    st.info(
        "스트림릿 클라우드의 Settings → Secrets에서 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 5. API 요청 및 오류 처리
# ---------------------------------------------------------

try:
    data = get_boxoffice(target_dt, api_key)

except requests.exceptions.Timeout:
    st.error("⏰ KOBIS API 요청 시간이 초과되었습니다.")
    st.info("잠시 후 다시 실행해 보거나 인터넷 연결 상태를 확인해 주세요.")
    st.stop()

except requests.exceptions.RequestException as e:
    st.error("🌐 KOBIS API에 접속하지 못했습니다.")
    st.info(
        "인터넷 연결 상태와 KOBIS API 주소가 정상인지 확인해 주세요."
    )
    st.stop()

except Exception:
    st.error("⚠️ 데이터를 불러오는 중 문제가 발생했습니다.")
    st.info(
        "KOBIS API 인증키와 스트림릿 Secrets 설정을 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 6. KOBIS API 자체 오류 확인
# ---------------------------------------------------------
# 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있습니다.
# 이때는 faultInfo가 들어옵니다.

if "faultInfo" in data:
    fault = data["faultInfo"]

    fault_message = fault.get(
        "message",
        "KOBIS API에서 오류가 발생했습니다."
    )

    st.error("❌ KOBIS API 오류")
    st.write(f"오류 내용: {fault_message}")

    st.info(
        "다음 사항을 확인해 주세요.\n\n"
        "• KOBIS 인증키(KOBIS_KEY)가 정확한지 확인\n"
        "• 스트림릿 Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지 확인\n"
        "• KOBIS API 사용이 가능한 인증키인지 확인"
    )

    st.stop()


# ---------------------------------------------------------
# 7. 영화 목록 가져오기
# ---------------------------------------------------------

try:
    boxoffice_result = data["boxOfficeResult"]
    movie_list = boxoffice_result["dailyBoxOfficeList"]
except (KeyError, TypeError):
    st.error("⚠️ KOBIS 응답에서 영화 목록을 찾을 수 없습니다.")
    st.info(
        "KOBIS API의 응답 형식이 정상인지 확인해 주세요."
    )
    st.stop()


# 영화 목록이 없는 경우
if not movie_list:
    st.warning("🎬 해당 날짜의 영화 목록이 없습니다.")
    st.info(
        f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')}\n\n"
        "KOBIS에서 해당 날짜의 박스오피스 자료가 아직 제공되지 않았거나, "
        "조회 날짜에 문제가 있을 수 있습니다."
    )
    st.stop()


# ---------------------------------------------------------
# 8. DataFrame으로 변환
# ---------------------------------------------------------

df = pd.DataFrame(movie_list)


# ---------------------------------------------------------
# 9. 숫자로 오는 값이 문자열이므로 숫자형으로 변환
# ---------------------------------------------------------
# 순위, 관객수, 누적관객수, 스크린수 등을 숫자로 바꿉니다.

number_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in number_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# 순위를 기준으로 정렬
df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------
# 10. 조회 날짜 표시
# ---------------------------------------------------------

st.subheader(
    f"📅 {yesterday.strftime('%Y년 %m월 %d일')} 박스오피스"
)


# ---------------------------------------------------------
# 11. 1위 영화 정보
# ---------------------------------------------------------

if len(df) > 0:

    first_movie = df.iloc[0]

    movie_name = first_movie["movieNm"]
    audience = int(first_movie["audiCnt"])
    total_audience = int(first_movie["audiAcc"])

    st.markdown(f"### 🥇 1위: {movie_name}")

    # 지표 카드 3개
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "어제 관객수",
            f"{audience:,}명"
        )

    with col2:
        st.metric(
            "누적 관객수",
            f"{total_audience:,}명"
        )

    with col3:
        st.metric(
            "스크린수",
            f"{int(first_movie['scrnCnt']):,}개"
        )


# ---------------------------------------------------------
# 12. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 그래프의 인덱스로 설정
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)


# ---------------------------------------------------------
# 13. 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎥 전체 박스오피스")

# 화면에 보여줄 열만 선택
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 보기 편하도록 열 이름을 한글로 변경
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자에 천 단위 쉼표 표시
display_df["관객수"] = display_df["관객수"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)

display_df["누적관객"] = display_df["누적관객"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)

display_df["스크린수"] = display_df["스크린수"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)


# 표 출력
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 14. 데이터 출처
# ---------------------------------------------------------

st.caption(
    "※ 데이터 출처: KOBIS 영화관입장권통합전산망 일별 박스오피스 API"
)
