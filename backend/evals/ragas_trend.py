from __future__ import annotations

import os


def main() -> None:
    if os.getenv("EDUNOVA_EVAL_ALLOW_NETWORK") != "1":
        print("Ragas 模型裁判未启用；设置 EDUNOVA_EVAL_ALLOW_NETWORK=1 后才允许联网趋势评测。")
        return
    import ragas  # noqa: F401

    print("Ragas 已就绪；项目固定硬门禁仍由 backend/evals/run.py 执行。")


if __name__ == "__main__":
    main()
