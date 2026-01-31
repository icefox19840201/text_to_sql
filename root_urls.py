import initapp
from urls.sys_urls import sys_router
app=initapp.fastapi_init()
app.include_router(sys_router,prefix='/default',tags=['自然语义查询'])
