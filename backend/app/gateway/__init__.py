"""AppGateway 网关包

Agent 隧道（控制 WS + 投屏数据面）与 internal RPC 的实现，由独立入口
backend/gateway_main.py 挂载，与业务 main.py 完全隔离。协议与部署形态见
docs/APP自动化-P1接口契约.md §2/§3/§9。
"""
