import datetime
import json
import streamlit as st
from google import genai

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="AI ผู้ช่วยตารางเรียนอัจฉริยะ", page_icon="🤖", layout="centered"
)

# 2. ปรับแต่ง CSS สำหรับกล่องแชทและปุ่มกด
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        .chat-header {
            text-align: center;
            padding: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid #e6e6e6;
        }

        .chat-row {
            display: flex;
            margin-bottom: 15px;
            width: 100%;
        }
        
        .chat-row.user {
            justify-content: flex-end;
        }
        
        .chat-row.assistant {
            justify-content: flex-start;
        }

        .chat-bubble {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 15px;
            font-size: 15px;
            line-height: 1.5;
            word-wrap: break-word;
        }

        .chat-row.user .chat-bubble {
            background-color: #2b5c8f;
            color: white;
            border-bottom-right-radius: 3px;
        }

        .chat-row.assistant .chat-bubble {
            background-color: #f1f0f0;
            color: #333333;
            border-bottom-left-radius: 3px;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# ส่วนหัวข้อของแชตบอต
st.markdown(
    """
    <div class="chat-header">
        <h2>🤖 AI ผู้ช่วยตารางเรียน</h2>
        <p style="color: gray; font-size: 14px;">สอบถามข้อมูลตารางสอน อาจารย์ผู้สอน หรือเวลาว่างได้ตลอด 24 ชั่วโมง</p>
    </div>
""",
    unsafe_allow_html=True,
)


# 3. โหลดข้อมูลตารางเรียน
@st.cache_data
def load_timetable():
  try:
    with open("timetable.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return None


# 4. โหลดชุดคำถาม-คำตอบ
@st.cache_data
def load_questions():
  try:
    with open("questions.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return []


timetable_data = load_timetable()
questions_data = load_questions()

if timetable_data is None:
  st.error(
      "⚠️ ไม่พบไฟล์ `timetable.json` ในโฟลเดอร์ กรุณาตรวจสอบไฟล์ข้อมูลอีกครั้ง"
  )
  st.stop()

# 5. ดึง API Key จาก Streamlit Secrets อย่างปลอดภัย
try:
  API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
  st.error(
      "⚠️ ยังไม่ได้ตั้งค่า `GEMINI_API_KEY` ในไฟล์ `.streamlit/secrets.toml`"
  )
  st.stop()

# สร้าง Client ของ Gemini
client = genai.Client(api_key=API_KEY)

# 6. จัดการประวัติการคุย (Chat History)
if "messages" not in st.session_state:
  st.session_state.messages = [
      {
          "role": "assistant",
          "content": (
              "สวัสดีครับ! ผมคือ AI ผู้ช่วยตารางเรียน สามารถสอบถามตารางสอน"
              " หรือเวลาว่างได้เลยครับ มีอะไรให้ช่วยไหมครับ?"
          ),
      }
  ]

# ตัวแปรสำหรับจำคำถามล่าสุดเผื่อเกิด Error
if "last_failed_prompt" not in st.session_state:
  st.session_state.last_failed_prompt = None

triggered_prompt = None

# --- ส่วนของปุ่มกดคำถามยอดฮิต (Quick Action Buttons) ---
st.write("💡 **คำถามยอดฮิต (คลิกเพื่อถามได้ทันที):**")
col1, col2, col3 = st.columns(3)

with col1:
  if st.button("📅 วันนี้วันอะไร / เรียนอะไร?"):
    triggered_prompt = "วันนี้วันอะไร และมีตารางสอนวิชาอะไรบ้าง?"
with col2:
  if st.button("📚 อาจารย์สอนวิชาอะไรบ้าง?"):
    triggered_prompt = "ครูผู้สอนสอนวิชาอะไรบ้าง และสอนห้องไหน?"
with col3:
  if st.button("☕ อาจารย์ว่างวันไหนบ้าง?"):
    triggered_prompt = "อาจารย์ว่างวันไหนบ้าง ไม่มีตารางสอน?"

# ถ้ามีประวัติคำถามที่เคย Error ค้างไว้ ให้แสดงปุ่ม "ลองส่งคำถามเดิมใหม่อีกครั้ง" ตรงนี้
if st.session_state.last_failed_prompt:
  st.warning(
      f'⚠️ ข้อความล่าสุด ("{st.session_state.last_failed_prompt}") ส่งไม่สำเร็จ'
      " เนื่องจากเซิร์ฟเวอร์หนาแน่น"
  )
  if st.button("🔄 คลิกที่นี่เพื่อลองส่งคำถามเดิมอีกครั้งทันที"):
    triggered_prompt = st.session_state.last_failed_prompt
    st.session_state.last_failed_prompt = (
        None  # ล้างค่า Error ออกหลังกดลองใหม่
    )

st.markdown("---")

# แสดงประวัติการสนทนาทั้งหมด
for message in st.session_state.messages:
  role = message["role"]
  content = message["content"]
  if role == "user":
    st.markdown(
        f'<div class="chat-row user"><div'
        f' class="chat-bubble">{content}</div></div>',
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        f'<div class="chat-row assistant"><div'
        f' class="chat-bubble">{content}</div></div>',
        unsafe_allow_html=True,
    )

# 7. รับข้อความจากช่องพิมพ์ปกติ (Chat Input)
chat_input_prompt = st.chat_input(
    "พิมพ์คำถามของคุณที่นี่ เช่น วันจันทร์เรียนอะไรบ้าง..."
)

if chat_input_prompt:
  triggered_prompt = chat_input_prompt
  st.session_state.last_failed_prompt = (
      None  # ถ้าพิมพ์ใหม่ ให้ล้างค่า Error เก่าทิ้ง
  )

# หากมีการกดปุ่ม คำถามยอดฮิต ปุ่มลองใหม่ หรือพิมพ์ข้อความเข้ามา
if triggered_prompt:
  # บันทึกข้อความผู้ใช้ลงประวัติ
  st.session_state.messages.append({"role": "user", "content": triggered_prompt})

  # แสดงผลฝั่งขวา
  st.markdown(
      f'<div class="chat-row user"><div'
      f' class="chat-bubble">{triggered_prompt}</div></div>',
      unsafe_allow_html=True,
  )

  # ดึงวันและเวลาปัจจุบันของระบบมาให้ AI รับรู้
  current_date = datetime.datetime.now().strftime("%Y-%m-%d")

  # กำหนด System Prompt ผสมข้อมูล JSON และวันที่ปัจจุบัน
  system_prompt = f"""
    คุณคือ AI ผู้ช่วยอัจฉริยะสำหรับตอบคำถามตารางเรียน
    ข้อมูลวันเวลาปัจจุบันของวันนี้คือ: {current_date}
    
    หน้าที่ของคุณคือตอบคำถามของผู้ใช้โดยอ้างอิงจากข้อมูล JSON ตารางเรียน และตัวอย่างชุดคำถามด้านล่างนี้
    หากผู้ใช้ถามว่า "วันนี้วันอะไร" หรือถามเกี่ยวกับวันเวลาปัจจุบัน ให้แจ้งวันที่ปัจจุบัน ({current_date}) ให้ผู้ใช้ทราบโดยอ้างอิงจากข้อมูลนี้
    
    [ข้อมูลตารางเรียนหลัก (JSON)]:
    {json.dumps(timetable_data, ensure_ascii=False)}

    [ตัวอย่างแนวทางการถามและตอบ (จากชุดคำถาม JSON)]:
    {json.dumps(questions_data, ensure_ascii=False)}
    
    กฎเหล็ก:
    - ให้ใช้ข้อมูลตารางเรียนด้านบนเป็นหลักในการตอบคำถาม
    - หากมีตัวอย่างในชุดคำถาม ให้ยึดรูปแบบและสไตล์การตอบตามตัวอย่างนั้น
    - ห้ามแต่งข้อมูลขึ้นมาเอง หากไม่มีข้อมูลใน JSON ให้ตอบว่า "ไม่พบข้อมูลตารางเรียนดังกล่าวในระบบ" (ยกเว้นเรื่องวันที่ปัจจุบันที่ระบบระบุให้)
    """

  # ประมวลผลคำตอบจาก AI
  with st.spinner("กำลังตรวจสอบตารางเรียน..."):
    try:
      contents = [f"System Context: {system_prompt}"]
      for m in st.session_state.messages:
        contents.append(f"{m['role']}: {m['content']}")

      # เรียกใช้โมเดล gemini-3.6-flash
      response = client.models.generate_content(
          model="gemini-3.6-flash", contents=contents
      )
      bot_reply = response.text

      # บันทึกและแสดงผลของบอตฝั่งซ้าย
      st.session_state.messages.append(
          {"role": "assistant", "content": bot_reply}
      )
      st.markdown(
          f'<div class="chat-row assistant"><div'
          f' class="chat-bubble">{bot_reply}</div></div>',
          unsafe_allow_html=True,
      )
      st.rerun()

    except Exception as e:
      # หากเกิด Error (เช่น 503) ให้จำคำถามนี้ไว้ และแสดงปุ่มกดลองใหม่
      if "503" in str(e) or "UNAVAILABLE" in str(e):
        st.session_state.last_failed_prompt = triggered_prompt
        st.error(
            "⚠️ เซิร์ฟเวอร์ AI มีผู้ใช้งานหนาแน่นชั่วคราว (Error 503)"
            " ระบบได้บันทึกคำถามของคุณไว้แล้ว สามารถกดปุ่ม **'🔄"
            " ลองใหม่อีกครั้ง'** ด้านบนได้เลยครับ"
        )
      else:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")