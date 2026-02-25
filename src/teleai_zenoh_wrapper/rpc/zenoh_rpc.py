import zenoh
import json
import time
import signal
import sys


def server():
    conf = zenoh.Config.from_json5(r'''
    {
        mode: "peer",
        listen: { endpoints: ["tcp/0.0.0.0:7887"] }
    }
    ''')

    session = zenoh.open(conf)

    # ──── 注册 RPC 服务 ────
    def on_query(query: zenoh.Query):
        """收到 RPC 请求时的回调"""
        key = str(query.selector)
        payload_bytes = bytes(query.payload) if query.payload else b"{}"
        request = json.loads(payload_bytes)

        print(f"📥 收到请求 [{key}]: {request}")

        # 业务逻辑：根据 key 路由到不同处理函数
        if "add" in key:
            result = {"sum": request.get("a", 0) + request.get("b", 0)}
        elif "multiply" in key:
            result = {"product": request.get("a", 0) * request.get("b", 0)}
        else:
            result = {"error": f"未知服务: {key}"}

        print(f"📤 返回响应: {result}")

        # 回复请求
        query.reply(
            query.key_expr,
            json.dumps(result).encode("utf-8"),
        )

    queryable = session.declare_queryable("rpc/math/*", on_query)
    print("🚀 RPC 服务已启动，监听 rpc/math/*")

    # 优雅退出
    def shutdown(sig, frame):
        print("\n正在关闭...")
        queryable.undeclare()
        session.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)


def client():
    conf = zenoh.Config.from_json5(r'''
    {
        mode: "peer",
        connect: { endpoints: ["tcp/127.0.0.1:7887"] }
    }
    ''')

    session = zenoh.open(conf)
    time.sleep(0.5)  # 等待连接建立

    # ──── 调用 RPC ────
    def rpc_call(service_key: str, params: dict, timeout_s: float = 5.0) -> dict:
        """
        同步 RPC 调用。

        Args:
            service_key: 服务路径，如 "rpc/math/add"
            params: 请求参数
            timeout_s: 超时秒数

        Returns:
            响应字典

        Raises:
            TimeoutError: 超时未收到响应
        """
        payload = json.dumps(params).encode("utf-8")

        replies = session.get(
            service_key,
            payload=payload,
            timeout=timeout_s,
        )

        for reply in replies:
            if reply.ok:
                return json.loads(bytes(reply.ok.payload))
            else:
                raise RuntimeError(f"RPC 错误: {reply.err}")

        raise TimeoutError(f"RPC 调用 {service_key} 超时 ({timeout_s}s)")

    # ──── 测试调用 ────
    print("=== RPC 客户端测试 ===\n")

    result = rpc_call("rpc/math/add", {"a": 10, "b": 20})
    print(f"add(10, 20) = {result}")

    result = rpc_call("rpc/math/multiply", {"a": 7, "b": 8})
    print(f"multiply(7, 8) = {result}")

    session.close()
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    import multiprocessing
    import time
    multiprocessing.set_start_method("spawn", force=True)

    server_p = multiprocessing.Process(target=server, name="server")
    client_p = multiprocessing.Process(target=client, name="client")

    server_p.start()
    time.sleep(1.0)
    client_p.start()

    client_p.join()
    server_p.join()