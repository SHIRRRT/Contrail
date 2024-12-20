import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import altair as alt
import datetime as dt

from GPU_query_db import *


COLOR_SCHEME = px.colors.qualitative.Plotly

DURATION = 30  # 查询时间范围：过去 30 秒
N_GPU = 8  # GPU 数量
GMEM = 80  # 显存：80 GB


def status_panel(gpu_current_df):
    for i in range(0, N_GPU, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j >= N_GPU:
                break
            with cols[j]:
                gpu_info = gpu_current_df.iloc[i + j]
                st.subheader(f"GPU {gpu_info['gpu_index']}")
                st.progress(gpu_info["gpu_utilization"] / 100, text=f"使用率：{gpu_info['gpu_utilization']}%")
                st.progress(
                    gpu_info["used_memory"] / 0x40000000 / GMEM,
                    text=f"显存用量：{gpu_info['used_memory']/0x40000000:.2f} GB",
                )


def webapp_realtime(hostname="Virgo", db_path="data/gpu_history_virgo.db"):
    DB_PATH = db_path  # 数据库路径

    st.title(f"{hostname}: 实时状态")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="autorefresh", value=True)

    with col3:
        if st.session_state["autorefresh"]:
            st_autorefresh(interval=1000, key="gpu_monitor_virgo")

    # 查询时间范围：过去 30 秒
    def get_time_range():
        end_time = dt.datetime.now(tz=dt.timezone.utc)
        start_time = end_time - dt.timedelta(seconds=DURATION)
        return start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")

    # 最新数据
    gpu_current_df = query_latest_gpu_info(DB_PATH)
    if not gpu_current_df.empty:
        current_timestamp = gpu_current_df["timestamp"].max()
        col2.write(f"更新于：{current_timestamp}")

    start_time, end_time = get_time_range()

    # 获取数据
    gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)

    # 如果没有数据，提示用户
    if gpu_utilization_df.empty:
        st.warning(f"过去 {DURATION} 秒内没有 GPU 数据记录：GPU 监控程序可能离线。")
    else:
        status_panel(gpu_current_df)

        st.divider()

        axis_end = dt.datetime.now() - dt.timedelta(seconds=1)
        axis_start = axis_end - dt.timedelta(seconds=DURATION)
        axis_x = (
            alt.X("timestamp:T").axis(labelSeparation=10).title(None).scale(alt.Scale(domain=(axis_start, axis_end)))
        )
        gpu_color = alt.Color("gpu_index:N").title("GPU").scale(domain=range(N_GPU), range=COLOR_SCHEME)

        select = st.pills(
            "信息选择",
            ["**详细信息**", "**用户使用**", "**汇总数据**"],
            default="**详细信息**",
            label_visibility="collapsed",
            selection_mode="single",
        )

        if select == "**详细信息**":
            gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
            gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)

            # GPU 每台设备的利用率折线图
            st.subheader("使用率 %")
            chart = (
                alt.Chart(gpu_utilization_df)
                .mark_line()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 100])),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            # GPU 内存使用情况
            st.subheader("显存用量 GB")
            chart = (
                alt.Chart(gpu_memory_df)
                .transform_calculate(memory="datum.used_memory / 0x40000000")
                .mark_line()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM])),
                )
            )
            st.altair_chart(chart, use_container_width=True)

        elif select == "**用户使用**":
            user_gpu_df = query_user_gpu_realtime_usage(start_time, end_time, DB_PATH)
            user_gpu_memory_df = query_user_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)

            user_dict = dict_username(DB_PATH)
            user_gpu_df["user"] = user_gpu_df["user"].map(user_dict)
            user_gpu_memory_df["user"] = user_gpu_memory_df["user"].map(user_dict)

            st.subheader("用户使用率 %")
            chart = (
                alt.Chart(user_gpu_df)
                .mark_area()
                .encode(
                    alt.Color("user:N").title("用户").scale(range=COLOR_SCHEME),
                    alt.Opacity("gpu_index:N").title("GPU"),
                    axis_x,
                    alt.Y("gpu_utilization:Q").title(None),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            st.subheader("用户显存用量 GB")
            chart = (
                alt.Chart(user_gpu_memory_df)
                .transform_calculate(memory="datum.used_memory / 0x40000000")
                .mark_area()
                .encode(
                    alt.Color("user:N").title("用户").scale(range=COLOR_SCHEME),
                    alt.Opacity("gpu_index:N").title("GPU"),
                    axis_x,
                    alt.Y("memory:Q").title(None),
                )
            )
            st.altair_chart(chart, use_container_width=True)

        elif select == "**汇总数据**":
            gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
            gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)

            # 总 GPU 使用率折线图
            st.subheader("总使用率 %")
            chart = (
                alt.Chart(gpu_utilization_df)
                .mark_area()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 800])),
                    alt.FillOpacityValue(0.5),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            # 总显存用量情况
            st.subheader("总显存用量 GB")
            chart = (
                alt.Chart(gpu_memory_df)
                .transform_calculate(memory="datum.used_memory / 0x40000000")
                .mark_area()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM * N_GPU])),
                    alt.FillOpacityValue(0.5),
                )
            )
            st.altair_chart(chart, use_container_width=True)
