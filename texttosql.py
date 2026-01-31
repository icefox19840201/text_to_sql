from langchain_classic.agents import AgentType
from langchain_classic.chains.sql_database.query import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit,create_sql_agent
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Dict,List,Optional
from langchain_core.prompts import PromptTemplate
from typing_extensions import TypedDict
import re,settings,traceback
from datetime import datetime
from pydantic import BaseModel,Field
from logger import logger

#------------------------------全局设置-------------------------------------------------
db=SQLDatabase.from_uri(settings.mysql_db_uri)
llm=ChatOpenAI(model='qwen3-max', temperature=0)
checkpoint=InMemorySaver()
#----------------------------定义状态图-----------------------------------------------------
class GraphState(TypedDict):
    user_query:str  #用户查询的问题
    generated_sql: Optional[str]  # query生成的SQL
    sql_validation: bool  # SQL语法是否有效
    sql_error: Optional[str]  # SQL相关错误信息
    exec_result: Optional[Dict]  # Agent执行结果
    formatted_result: Optional[str]  # 格式化后的最终结果
    retry_count: int  # 重试次数
    streaming_queue: List[str]  # 流式消息队列
    streaming_progress: str  # 当前流式进度消息
    echarts:Optional[Dict] # Echar数据
    has_echar_data:bool   #是否有echar数据
    conversation_history: List[Dict]  # 对话历史记录
    last_sql: Optional[str]  # 上一次执行的SQL
#------------------------------获取对话历史------------------------------------------------
async def get_conversation_history(state:GraphState):
    conversation_history_str=''
    if state.get("conversation_history"):
        logger.info(f"对话历史记录数: {len(state['conversation_history'])}")
        for item in state["conversation_history"]:
            conversation_history_str += f"用户: {item.get('user_query', '')}\n"
            if item.get('generated_sql'):
                conversation_history_str += f"SQL: {item['generated_sql']}\n"
            conversation_history_str += "---\n"
        logger.info(f"对话历史字符串: {conversation_history_str}")
    else:
        logger.warning("对话历史为空")
    print(conversation_history_str)
    return conversation_history_str
#------------------------------提取查询关键词中的返回数量------------------------------------
def extract_top_k_from_query(query: str) -> int:
    """从用户查询中提取top_k值，默认为5"""
    # 转换为小写便于匹配
    query_lower = query.lower()
    # 匹配"前N"、"top N"、"前N个"等模式
    patterns = [
        r'前\s*(\d+)\s*个',
        r'top\s*(\d+)',
        r'前\s*(\d+)',
        r'(\d+)\s*个',
        r'(\d+)\s*条'
    ]

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            try:
                top_k = int(match.group(1))
                # 限制范围在1-50之间
                return max(1, min(top_k, 50))
            except ValueError:
                continue

    # 默认返回5
    return 5
#-------------------------------定义变量---------------------------------
query_top_k=5   #定义查询结果数量
#-----------------------------定义适合性评分----------------------------
class DataNeedImage(BaseModel):
    # 定义binary_score字段，表示是否适合生成报表，取值为"yes"或"no"
    binary_score: str = Field(description="是否适合生成报表，取值为 'yes' 或 'no'")
class DataSchema(BaseModel):
    """数据结构定义"""
    echar_data:Dict=Field(description="echar数据,取值为json数据")
#------------------------------模板定义----------------------------------
sql_template='''
你是专业的MySQL SQL生成专家，
你的责职如下：
   1:仅生成查询SQL语句，无额外解释；
   2：表结构：{table_info}
   3：严禁生成任何可以影响数据库数据内容或结构的sql
   4：最多返回{top_k}条记录
   5：你需要准确理解表结构及字段含义并理解用户的需求后生成sql
   6：如果用户的问题是对上一次查询结果的修改或补充（例如"只需要前两条"、"再查一下"、"换个条件"等），请基于上一次的SQL进行修改，而不是重新生成新的SQL
   7：考虑对话历史，理解用户的真实意图
   8：特别注意：当用户说"只需要N条"、"前N条"、"只要N个"等时，应该基于上一次的SQL，只修改LIMIT子句
   9:用户如无特别说明，每次查询返回前10条数据
   对话历史：
   {conversation_history}
   上一次执行的SQL：
   {last_sql}
   用户需求：{input}
'''

sql_agent_template=f'''
你是一个SQL执行和校准专家。
你的任务是：
    1. 检查SQL语法是否正确
    2. 执行SQL查询并返回结果
    3. 如果SQL有误，先尝试修正再执行
    4. 返回清晰、准确的查询结果
    5. 返回清晰的查询结果，查询的结果用markdown格式返回
    6.对查询结果进行总结描述
    7. 深刻理解用户需求与表节构，可以参考历史对话
        表结构：{db.get_table_info()}
        
注意：
     1：充分理解表结构后，分析sql查询是否满足查询要求,如果不能满足查询需求，请修正 SQL
     2. 先检查SQL语法是否正确,准确理解用户需求，并准确理解数据库的结构与字段含义
     3 检查sql查询是否包含危险操作，如果包含，请拒绝执行
     4.执行查询并获取结果
     5. 如果查询有误，请修正后重新执行
     6：如果查询失败即无数据，明确告知用户原因，并提供排错的建议
     7:输出的结果，列名全部显示中文
'''
#-----------------------------定义查询链生成sql-----------------------------------
sql_prompt=PromptTemplate(
    input_variables=['input','table_info','top_k','conversation_history','last_sql'],
    template=sql_template,
)
sql_query_chain=create_sql_query_chain(llm=llm,db=db,prompt=sql_prompt,k=query_top_k)
#----------------------------定义sqlagent负责校验执行-------------------------------------------
#Sql Toolkit +Agent (校验执行Sql)
toolkit=SQLDatabaseToolkit(db=db,llm=llm)
sql_exec_agent=create_sql_agent(llm=llm,
                                toolkit=toolkit,
                                agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                                verbose=False,
                                handle_parsing_errors=True,
                                max_iterations=5, #增加迭代次数，允许sqlagent修正sql
                                return_intermediate_steps=True,
                                #添加提示词
                                prefix=sql_agent_template
 )

#----------------------------图节点处理--------------------------------------------------


async  def generate_sql_node(state:GraphState):
    '''
    生成sql
    :param state:
    :return:
    '''

    # 添加第一个进度信息
    try:
        state["streaming_progress"] = "🔄 正在分析用户需求,生成相应的Sql查询..."
        state["streaming_queue"].append(state["streaming_progress"])
        yield state
        #生成 sql
        top_k = extract_top_k_from_query(state["user_query"])
        global query_top_k
        query_top_k=top_k

        # 构建对话历史字符串
        conversation_history_str =await get_conversation_history(state)
        # 获取上一次的SQL
        last_sql = state.get("last_sql", "")
        sql=''
        async for chunk in sql_query_chain.astream({
            'question': state['user_query'],
            "table_info": db.get_table_info(),
            "top_k": top_k,
            "conversation_history": conversation_history_str,
            "last_sql": last_sql
        }):
            sql += str(chunk)

        generated_sql=sql.strip()
        state["streaming_progress"] = "✅ SQL生成完成"
        state["streaming_queue"].append(state["streaming_progress"])
        state["generated_sql"] = generated_sql
        state["sql_validation"] = True
        state["sql_error"] = None
        yield state
    except Exception as e:
        msg=traceback.format_exc()
        state["streaming_progress"] = f"❌ SQL生成失败：{str(e)}"
        state["streaming_queue"].append(state["streaming_progress"])
        state["sql_validation"] = False
        state["sql_error"] = msg
        logger.error(msg)
        yield state

async def validate_sql_node(state:GraphState):
    '''
    校验sql的合法性
    :param state:
    :return:
    '''
    if not state.get('generated_sql'):
        state["streaming_progress"] = "❌ SQL未生成或生成失败"
        state["sql_validation"] = False
        state["streaming_queue"].append(state["streaming_progress"])
        yield state
        return
    state['streaming_progress']='正在校验sql语句的合规性'
    sql=state['generated_sql'].upper().strip()
    dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']
    for keyword in dangerous_keywords:
        if keyword in sql:
            state["streaming_progress"] = f"❌ SQL包含危险操作：{keyword}"
            state["streaming_queue"].append(state["streaming_progress"])
            state["sql_validation"] = False
            state["sql_error"] = f"SQL包含危险操作：{keyword}"
            yield state
            return
    # 如果sql_validation尚未被设置为False（即没有危险操作），则校验通过
    if state['sql_validation'] != False:
        state["streaming_progress"] = "✅ SQL语法校验通过，进入查询"
        state["sql_validation"] = True
        state["streaming_queue"].append(state["streaming_progress"])
        yield state
async def execute_sql_node(state:GraphState):
    '''
    执行sql
    :param state:
    :return:
    '''
    try:
        state["streaming_progress"] = '🚀 准备执行SQL查询...'
        state["streaming_queue"].append(state["streaming_progress"])
        yield state
        if state["sql_validation"] == False:
            state["streaming_progress"] = '❌ SQL未通过校验，跳过执行'
            state["streaming_queue"].append(state["streaming_progress"])
            yield state
            state["exec_result"] = None
            yield state
            return
        state["streaming_progress"] = '🚀 正在执行SQL查询...'
        state["streaming_queue"].append(state["streaming_progress"])
        yield state
        conversation_history_str = await get_conversation_history(state)
        # 获取上一次的SQL
        last_sql = state.get("last_sql", "")
        sql_with_context = f"""
                 初始生成SQL: {state['generated_sql']}
                 用户需求：{state['user_query']}    
                  历史对话： "conversation_history": {conversation_history_str},       
                """
        #exec_result=sql_exec_agent.astream({'input':sql_with_context,'conversation_history': conversation_history_str,'last_sql': last_sql})
        async for chunk in sql_exec_agent.astream({'input':sql_with_context,'conversation_history': conversation_history_str,'last_sql': last_sql}):
            if isinstance(chunk,dict):
                if 'output' in chunk:
                    state["exec_result"] = {
                        "raw_output": chunk['output'],
                        "intermediate": chunk.get("intermediate_steps", [])
                    }
                    state['sql_error'] = None
                    yield state
    except Exception as e:
        msg=traceback.format_exc()
        state["streaming_progress"] = f"❌ SQL执行失败：{str(e)}"
        state["streaming_queue"].append(state["streaming_progress"])
        state["exec_result"] = None
        state["sql_error"] = '查询过程中发生错误'
        logger.error(msg)
        yield state
async def format_result_node(state:GraphState):
    '''
    格式化结果
    :param state:
    :return:
    '''
    try:
        if not state["exec_result"] or state["exec_result"].get("raw_output") is None:
            error_msg = state.get('sql_error', '未知错误')
            state["streaming_progress"] = f"❌ 查询失败：{error_msg}"
            state["formatted_result"] = f"查询失败：{error_msg}"
            state["streaming_queue"].append(state["streaming_progress"])
            yield state
            return

        state["streaming_progress"] = "🎨 正在格式化查询结果..."
        state["streaming_queue"].append(state["streaming_progress"])
        yield state

        # 提取Agent的执行结果
        raw_output = state["exec_result"]["raw_output"]
        intermediate_steps = state["exec_result"]["intermediate"]

        # 分析Agent的响应，提取有用的信息
        if not raw_output or raw_output.strip() == "":
            result_text = "未查询到符合条件的数据"
        elif "error" in raw_output.lower():
            result_text = f"查询出现错误：{raw_output}"
        else:
            # 清理和格式化Agent的输出
            result_text = raw_output.strip()

        # 构建最终回复，包含SQL和结果
        formatted = f"""### 🎯 查询结果
                        {result_text}
                    """

        state["streaming_progress"] = "✅ 结果格式化完成"
        state["formatted_result"] = formatted
        state["streaming_queue"].append(state["streaming_progress"])
        # 更新对话历史（在工作流节点中直接更新，让 checkpointer 自动保存）
        history_conversation = state.get("conversation_history", [])
        history_generated_sql = state.get("generated_sql")
        # 创建新的对话记录
        new_record = {
            "user_query": state.get("user_query"),
            "generated_sql": history_conversation,
            "timestamp": str(datetime.now())
        }
        print('当前数据：',history_generated_sql)
        print('更新数据：',new_record)
        # 添加到对话历史（最多保留最近10条）
        updated_history = history_conversation + [new_record]
        print('更新数据：',updated_history)
        if len(updated_history) > 10:
            updated_history = updated_history[-10:]
        # 更新状态
        state["conversation_history"] = updated_history
        state["last_sql"] = history_generated_sql
        
        logger.info(f"已保存对话记录，当前历史记录数: {len(updated_history)}")
        
        yield state
    except Exception as e:
        msg=traceback.format_exc()
        state["streaming_progress"] = f"❌ 结果格式化失败：{str(e)}"
        state["formatted_result"] = f"结果格式化失败：{str(e)}"
        state["streaming_queue"].append(state["streaming_progress"])
        logger.error(msg)
        yield state

async def retry_generate_sql_node(state:GraphState):
    '''
    重试生成sql
    :param state:
    :return:
    '''
    state["streaming_progress"] = f"🔄 第{state['retry_count'] + 1}次重试生成SQL..."
    state["streaming_queue"].append(state["streaming_progress"])
    state["retry_count"] = state["retry_count"] + 1
    state["generated_sql"] = None  # 清空原有SQL
    state["sql_validation"] = False
    yield state
#----------------------------定义动态路由-----------------------------------------
async def sql_validate_route(state:GraphState):
    '''
    定义动态路由
    :param state:
    :return:
    '''
    if state['sql_validation']==True:
        return 'execute_sql'
    elif state['retry_count']<=2:
        return 'retry_generate_sql'
    return 'format_result'

async def gen_image_node(state:GraphState):
    '''
    将查询结果处理为适合做echar数据报表的格式并生成对应的格式
    :param state:
    :return:
    '''
    try:
        content=state['exec_result']['raw_output']
        prompts=PromptTemplate.from_file('prompts/data_report_template.txt',encoding='utf-8')
        chain=prompts|llm.with_structured_output(DataSchema)
        result=await chain.ainvoke({'content':content})
        echar=result.echar_data
        state['echarts']=echar
        yield state
    except Exception as e:
        msg=traceback.format_exc()
        state['streaming_progress'] = f"❌ 生成图表失败：{str(e)}"
        state['streaming_queue'].append(state['streaming_progress'])
        logger.error(msg)
        yield state
async def after_query_route(state:GraphState):
    '''
    定义是否生成报表的动态路由
    :param state:
    :return:
    '''
    if state.get('has_echar_data'):
        return 'gen_image'
    else:
        return END
async def before_genimage_node(state:GraphState):
    '''
    查到数据后，是否适合生数据报表的
    :param state:
    :return:
    '''
    try:
        if state.get('exec_result') is None or state.get('exec_result').get('raw_output') is None:
            state['has_echar_data']=False
            state["streaming_queue"].append('无适当数据生成图表')
        else:
            execnode_data=state['exec_result']['raw_output']
            questtion=state['user_query']
            prompt=PromptTemplate.from_file('prompts/prompt_template_grade.txt',encoding='utf-8')
            chain=prompt|llm.with_structured_output(DataNeedImage)
            result=await chain.ainvoke({'context':execnode_data,'question':questtion})
            isneed=result.binary_score
            if isneed=='yes':
                state['has_echar_data']=True
                state["streaming_queue"].append('准备生成数据报表')
            else:
                state['has_echar_data']=False
                state["streaming_queue"].append('不需要生成数据报表')
        yield state
    except Exception as e:
        msg=traceback.format_exc()
        state['streaming_progress'] = f"❌ 获取数据报表生成失败"
        state['streaming_queue'].append(state['streaming_progress'])
        logger.error(msg)
        yield state

#----------------------------定义工作流----------------------------------------------
async def workflow():
    graph=StateGraph(GraphState)
    #添加处理节点
    graph.add_node('generate_sql', generate_sql_node)
    graph.add_node('validate_sql',validate_sql_node)
    graph.add_node('retry_generate_sql',retry_generate_sql_node)
    graph.add_node('execute_sql',execute_sql_node)
    graph.add_node('format_result',format_result_node)
    graph.add_node('before_genimage', before_genimage_node)
    graph.add_node('gen_image', gen_image_node)
    #添加边
    graph.add_edge(START,'generate_sql')
    # #生成sql->检验sql
    graph.add_edge('generate_sql','validate_sql')
    # #动态路由，根据校验的结果进行下一步动作的判断,(执行，重试，结束)
    graph.add_conditional_edges('validate_sql',sql_validate_route,{'execute_sql':'execute_sql',
                                                                   'retry_generate_sql':'retry_generate_sql',
                                                                   'format_result':'format_result'})
    # #重试->>生成sql
    graph.add_edge('retry_generate_sql','generate_sql')
    # #执行sql->格式化结果
    graph.add_edge('execute_sql','format_result')
    graph.add_edge('format_result','before_genimage')
    graph.add_conditional_edges('before_genimage',after_query_route,{'gen_image':'gen_image',END:END})
    # 启用 checkpoint 记忆功能
    return graph.compile(checkpointer=checkpoint)
#----------------------------查询接口------------------------------------------------
async  def stream_sql_query(user_query, sid=1):
    '''
    调用工作流进行查询处理
    :param user_query: 用户查询问题
    :param sid: 会话ID，用于记忆功能
    :return:
    '''
    # user_query='查询市盈率（TTM）大于 30 的股票名称、市盈率、持仓机构名称、持仓占比及持仓成本，按市盈率降序排序。查找前20条数据'
    yield f'开始处理,用户问题：{user_query}\n'
    yield '-'*50+'\n'
    sqlflag=False
    graph_agent=await workflow()
    # graph_agent.get_graph().draw_png('workflow.png')
    yield "工作流已编译完成，开始流程任务\n"
    # 配置 thread_id 用于记忆功能
    config = {
        "configurable": {
            "thread_id": str(sid)
        }
    }

    # # 初始状态（不包含 conversation_history 和 last_sql，让 checkpointer 自动恢复）
    current_state = {
        "user_query": user_query,
        "generated_sql": None,
        "sql_validation": None,
        "sql_error": None,
        "exec_result": None,
        "formatted_result": None,
        "retry_count": 0,
        "streaming_queue": [],
        "streaming_progress": "",
        "echarts":None,
        "has_echar_data":None
    }
    
    # 用于跟踪已经输出过的消息，防止重复输出
    previous_progress = set()
    
    # 处理工作流的流式输出
    yield "开始执行工作流...\n"
    try:
        async for state in graph_agent.astream(current_state, config=config, stream_mode="updates"):
            for node_name, node_states in state.items():
                if isinstance(node_states, dict) and node_states.get("streaming_progress"):
                    if  node_states.get("streaming_queue"):
                        all_node_state=node_states.get("streaming_queue")
                        for item_node_state in all_node_state:
                            # 只输出之前没有输出过的消息
                            if item_node_state not in previous_progress:
                                yield item_node_state
                                previous_progress.add(item_node_state)
                if sqlflag==False:
                    if isinstance(node_states, dict):
                        if node_states.get('generated_sql'):
                            yield f"首次生成的SQL: {node_states.get('generated_sql')}\n"
                            sqlflag=True
                # 检查是否有echarts数据，并且has_echar_data为True
                if isinstance(node_states, dict) and node_states.get('echarts') and node_states.get('has_echar_data'):
                    echarts = node_states.get('echarts')
                    print(echarts)
                    yield f"{echarts}\n"
                # 返回has_echar_data字段，前端根据该字段判断是否需要生成数据报表
                if isinstance(node_states, dict) and 'has_echar_data' in node_states:
                    yield {'has_echar_data': node_states.get('has_echar_data')}
            # 获取格式化结果
            format_result = None
            if 'format_result' in state:
                format_result = state['format_result'].get('formatted_result')
            elif 'formatted_result' in state:
                format_result = state.get('formatted_result')
            if format_result:
                yield f"{format_result}\n"
        
        yield "工作流执行完成。\n"
    except Exception as e:
        msg=traceback.format_exc()
        logger.error(msg)
        yield f"工作流执行出错: {msg}\n"
