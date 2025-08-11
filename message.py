# message.py - 社区留言板（双语支持）
import streamlit as st
import psycopg2
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ DATABASE_URL is not set. Please check your .env file.")
    st.stop()

# Parse the database URL
try:
    url = urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host": url.hostname,
        "port": url.port,
        "database": url.path[1:],  # Strip leading '/'
        "user": url.username,
        "password": url.password,
    }
except Exception as e:
    st.error(f"❌ Failed to parse database URL: {e}")
    st.stop()


# -----------------------------
# Database Connection
# -----------------------------
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"🔗 Database connection failed: {e}")
        return None


# -----------------------------
# Load paginated posts and all comments
# -----------------------------
def load_posts_with_comments(limit=20, offset=0, t=None):
    """
    加载分页帖子和所有评论
    :param limit: 每页数量
    :param offset: 偏移量
    :param t: 翻译函数（用于错误提示）
    :return: posts, total_count
    """
    conn = get_db_connection()
    if not conn:
        st.error(t("message_failed_load").format(error="Connection failed"))
        return [], 0

    try:
        with conn.cursor() as cur:
            # Count total posts
            cur.execute("SELECT COUNT(*) FROM posts")
            total_count = cur.fetchone()[0]

            # Load paginated posts
            cur.execute("""
                SELECT id, title, content, author, created_at
                FROM posts
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            post_rows = cur.fetchall()

            # Load ALL comments
            cur.execute("""
                SELECT id, post_id, parent_comment_id, author, content, created_at
                FROM comments
                ORDER BY created_at ASC
            """)
            comment_rows = cur.fetchall()

            # Build posts
            posts = []
            for row in post_rows:
                post = {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "author": row[3],
                    "created_at": row[4],
                    "comments": []
                }
                # Attach comments
                for cmt in comment_rows:
                    if cmt[1] == post["id"]:
                        post["comments"].append({
                            "id": cmt[0],
                            "post_id": cmt[1],
                            "parent_comment_id": cmt[2],
                            "author": cmt[3],
                            "content": cmt[4],
                            "created_at": cmt[5]
                        })
                posts.append(post)

            return posts, total_count
    except Exception as e:
        st.error(t("message_failed_load").format(error=str(e)))
        return [], 0
    finally:
        conn.close()


# -----------------------------
# Create new post
# -----------------------------
def create_post(title, content, author, t=None):
    """
    创建新帖子
    :param title: 标题
    :param content: 内容
    :param author: 作者
    :param t: 翻译函数
    """
    conn = get_db_connection()
    if not conn:
        st.error(t("message_failed_post").format(error="DB connection failed"))
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO posts (title, content, author) VALUES (%s, %s, %s)",
                (title, content, author)
            )
            conn.commit()
        st.success(t("message_success"))
    except Exception as e:
        st.error(t("message_failed_post").format(error=str(e)))
    finally:
        conn.close()


# -----------------------------
# Create comment or reply
# -----------------------------
def create_comment(post_id, content, author, t=None, parent_comment_id=None):
    """
    创建评论或回复
    :param post_id: 帖子 ID
    :param content: 评论内容
    :param author: 作者
    :param parent_comment_id: 父评论 ID（如果是回复）
    :param t: 翻译函数
    """
    conn = get_db_connection()
    if not conn:
        st.error(t("message_failed_comment").format(error="DB connection failed"))
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO comments (post_id, content, author, parent_comment_id) VALUES (%s, %s, %s, %s)",
                (post_id, content, author, parent_comment_id)
            )
            conn.commit()
        st.success(t("message_comment_posted"))
    except Exception as e:
        st.error(t("message_failed_comment").format(error=str(e)))
    finally:
        conn.close()


# -----------------------------
# 主入口函数（接收 t 函数）
# -----------------------------
def render(t):
    """
    渲染留言板页面
    :param t: 翻译函数，t(key) -> str
    """
    st.title(t("message_community_title"))
    st.markdown(t("message_community_intro"))

    # 用户昵称
    if "author_name" not in st.session_state:
        st.session_state.author_name = ""

    author_name = st.text_input(
        t("message_nickname"),
        value=st.session_state.author_name
    )
    st.session_state.author_name = author_name.strip() or "Anonymous"

    st.markdown("---")

    # 创建新帖子
    with st.expander(t("message_create_topic"), expanded=False):
        with st.form("new_post_form"):
            title = st.text_input(t("message_post_title"))
            content = st.text_area(t("message_post_content"), height=100)
            submit = st.form_submit_button(t("message_publish"))
            if submit and title.strip() and content.strip():
                create_post(
                    title=title.strip(),
                    content=content.strip(),
                    author=st.session_state.author_name,
                    t=t  # 传入 t
                )
                st.rerun()

    st.markdown(f"## {t('message_active_topics')}")

    # 分页设置
    PAGE_SIZE = 20
    if "page" not in st.session_state:
        st.session_state.page = 0
    if st.session_state.page < 0:
        st.session_state.page = 0

    offset = st.session_state.page * PAGE_SIZE
    posts, total_count = load_posts_with_comments(limit=PAGE_SIZE, offset=offset, t=t)
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

    if total_count == 0:
        st.info(t("message_no_posts"))
        return

    # 显示帖子
    for post in posts:
        with st.container():
            st.markdown(f"### {post['title']}")
            st.markdown(f"> {post['content']}")
            st.caption(f"👤 {post['author']} · {post['created_at'].strftime('%Y-%m-%d %H:%M')}")

            # 顶层评论
            top_level_comments = [
                c for c in post["comments"]
                if c["parent_comment_id"] is None
            ]

            if not top_level_comments:
                st.markdown("*No comments yet.*")

            for comment in top_level_comments:
                with st.expander(
                    f"💬 {comment['author']}: {comment['content'][:30]}...",
                    expanded=False
                ):
                    st.markdown(f"**{comment['author']}**: {comment['content']}")
                    st.caption(f"📅 {comment['created_at'].strftime('%Y-%m-%d %H:%M')}")

                    # 显示回复
                    replies = [
                        r for r in post["comments"]
                        if r["parent_comment_id"] == comment["id"]
                    ]
                    for reply in replies:
                        st.markdown(
                            f"""
                            <div style="
                                margin: 0.5rem 0;
                                padding: 0.5rem;
                                background-color: #f0f2f6;
                                border-radius: 8px;
                                border-left: 4px solid #1f77b4;
                                font-size: 0.95em;
                            ">
                                <strong>{reply['author']}</strong>: {reply['content']} 
                                <span style="color: #666; font-size: 0.8em;">
                                    · {reply['created_at'].strftime('%Y-%m-%d %H:%M')}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    # 回复表单
                    with st.form(key=f"reply_form_{comment['id']}"):
                        reply_content = st.text_area(
                            t("message_reply_placeholder"),
                            height=60,
                            key=f"reply_input_{comment['id']}"
                        )
                        reply_submit = st.form_submit_button(t("message_reply_button"))
                        if reply_submit and reply_content.strip():
                            create_comment(
                                post_id=post["id"],
                                content=reply_content.strip(),
                                author=st.session_state.author_name,
                                parent_comment_id=comment["id"],
                                t=t  # ✅ 传入 t
                            )
                            st.rerun()

            # 帖子评论表单
            with st.form(key=f"comment_form_{post['id']}"):
                comment_content = st.text_area(
                    t("message_comment_placeholder"),
                    height=60,
                    key=f"comm_input_{post['id']}"
                )
                comment_submit = st.form_submit_button(t("message_comment_button"))
                if comment_submit and comment_content.strip():
                    create_comment(
                        post_id=post["id"],
                        content=comment_content.strip(),
                        author=st.session_state.author_name,
                        parent_comment_id=None,
                        t=t  # ✅ 传入 t
                    )
                    st.rerun()

        st.markdown("---")

    # 分页控件
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    prev_disabled = st.session_state.page <= 0
    next_disabled = st.session_state.page >= total_pages - 1

    with col_left:
        if st.button(t("message_prev"), disabled=prev_disabled):
            st.session_state.page -= 1
            st.rerun()

    with col_mid:
        st.markdown(
            f"<p style='text-align: center; margin-top: 1rem;'>{t('message_page_info').format(current=st.session_state.page + 1, total=total_pages)}</p>",
            unsafe_allow_html=True
        )

    with col_right:
        if st.button(t("message_next"), disabled=next_disabled):
            st.session_state.page += 1
            st.rerun()