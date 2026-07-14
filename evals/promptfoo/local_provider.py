from __future__ import annotations

import sys


sys.stdout.reconfigure(encoding="utf-8")
prompt = sys.stdin.read().strip() or " ".join(sys.argv[1:]).strip()
if "引用" in prompt:
    print("回答只绑定已确认资料的证据引用；证据不足时明确降级。")
else:
    print("启发函数估计当前位置到目标的代价，帮助 A* 搜索优先扩展更有希望的节点。")
