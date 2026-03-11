import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

SYSTEM_PROMPT = """You are a friendly and professional receptionist for Acme Dental clinic.
Your job is to help patients by:
- Answering questions about the clinic's services, hours, and location
- Scheduling, rescheduling, or cancelling appointments
- Providing general dental information

Always be warm, concise, and professional. If you cannot help with something,
direct the patient to call the clinic directly."""


@tool
def get_clinic_info() -> str:
    """Returns general information about Acme Dental clinic."""
    return (
        "Acme Dental Clinic - Hours: Mon-Fri 8am-6pm, Sat 9am-2pm. "
        "Services: general dentistry, cleanings, fillings, whitening, orthodontics. "
        "Phone: (555) 123-4567. Address: 123 Main St."
    )


tools = [get_clinic_info]

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
