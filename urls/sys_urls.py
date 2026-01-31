from fastapi import APIRouter
from core.views.default import default,query
sys_router=APIRouter()
sys_router.add_api_route('/index',default,methods=["GET"])
sys_router.add_api_route('/query',query,methods=["POST"])

