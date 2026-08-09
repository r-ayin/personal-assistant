"""import_knowledge.py — 将 Hermes 个人知识直接注入 PA 记忆系统"""
import os, sys, re

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '.')

from personal_assistant import storage, distill, llm

ENTRIES = [
    # 身份
    {"kind": "fact", "content": "用户微信主账号：wxid_ts58chree3kx22，使用 WeChat 4.x"},
    {"kind": "fact", "content": "用户阿里云 ECS 服务器：115.29.199.130，root 用户，ed25519 SSH 密钥 ~/.ssh/dolt_recovery"},
    {"kind": "fact", "content": "用户 GitHub/代码平台：code.alibaba-inc.com/xiqxhq"},
    
    # 技术领域
    {"kind": "knowledge", "content": "用户从事量化金融/因子挖掘方向：广发 CogAlpha 全自动因子挖掘 + moni GPU 因子工厂融合，21 智能体 × 5 模式因子生成框架"},
    {"kind": "knowledge", "content": "用户使用 DeepSeek 为主要 LLM 后端，辅以 Claude/Kimi Code/GLM-5.2。本机无 GPU/torch，优先 stdlib + 已装包"},
    {"kind": "knowledge", "content": "用户做 ESP32-S3 嵌入式开发：双模式固件 WakeWord + 背景音频，I2S/PCM/OPUS 管线"},
    {"kind": "skill", "content": "用户全栈：Python FastAPI/SQLite、React/Next.js、Android Kotlin"},
    {"kind": "knowledge", "content": "用户做 A 股分钟数据流水线：pytdx 通达信渠道，补缺→指标→采集器"},
    
    # 活跃项目
    {"kind": "fact", "content": "用户核心项目：personal-assistant（个人数字分身助手，ESP32 24h 监听 + 记忆蒸馏 + 对话/日历/提醒）"},
    {"kind": "fact", "content": "用户项目：moni GPU 因子工厂，CogAlpha 融合报告+路线图已定"},
    {"kind": "fact", "content": "用户项目：douyin 抖音内容管线，God-tier deep research + 四步 QA"},
    {"kind": "fact", "content": "用户项目：wechat 每日热点日报，Hermes Gateway 驱动"},
    {"kind": "fact", "content": "用户项目：钉钉考勤自动导出"},
    {"kind": "fact", "content": "用户项目：pachong-master 招标信息爬虫"},
    {"kind": "fact", "content": "用户项目：wanxia 小红书封面生成"},
    
    # 基础设施
    {"kind": "fact", "content": "ECS bare git repos：/root/git-repos/ 含 moni/autonomous-studio/personal-assistant 三个项目"},
    {"kind": "fact", "content": "用户全项目凭据总表：E:\\x-tool\\credentials-reference.md"},
    {"kind": "fact", "content": "用户基础设施总表：E:\\x-tool\\infrastructure-reference.md"},
    {"kind": "fact", "content": "用户 TaskBoard：E:\\x-tool\\TASKBOARD.md，每 5 分钟自动刷新"},
    
    # 开发习惯
    {"kind": "preference", "content": "用户偏好自主模式：AI 引擎默认活跃执行，不等触发词，commit 后直接 git push"},
    {"kind": "preference", "content": "用户开发规范：所有中文输出必须在 CJK-Latin 字符间自动加空格"},
    {"kind": "preference", "content": "用户开发原则：反幻觉优先——涉及事实必须先搜证，不凭记忆写，确定性 > LLM 自评"},
    
    # 运行环境
    {"kind": "fact", "content": "用户本机：Windows 11，Python 3.12，Clash 代理 127.0.0.1:7890，pip 直连 PyPI 超时需走代理"},
    {"kind": "fact", "content": "用户 Windows 环境已积累坑清单：fake-IP 污染/GBK 编码/Hermes venv 补丁/计划任务"},
    {"kind": "fact", "content": "用户 Hermes Gateway 已从 WSL 迁至 Windows，四渠道全通，计划任务驱动"},
]

def main():
    total = 0
    # 1. 写入记忆
    for i, entry in enumerate(ENTRIES):
        mem = {
            "id": f"mk-import-{i:04d}",
            "segment_id": "hermes-knowledge-import",
            "kind": entry["kind"],
            "content": entry["content"],
            "evidence": "source: hermes-agent-memory-import-2026-07-25",
        }
        try:
            storage.add_memory(mem, None)
            total += 1
        except Exception as e:
            print(f"  [skip] {e}")

    print(f"  Wrote {total} memories")

    # 2. 蒸馏人格
    print("  Running persona distillation...")
    try:
        n = distill.run()
        print(f"  Distilled: {n} new observations")
        profile = distill.load_persona()
        if profile:
            meta = profile.get("_meta", {})
            print(f"  Profile v{meta.get('version', '?')}: {json.dumps(profile, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  Distillation failed: {e}")

    # 3. 验证
    con = storage.connect()
    try:
        count = con.execute("SELECT COUNT(*) FROM memories WHERE segment_id='hermes-knowledge-import'").fetchone()[0]
        print(f"\n  Verified: {count} memories in DB")
    finally:
        con.close()
    
    print(f"\n  Done: {total} entries imported")

if __name__ == '__main__':
    import json
    print("Importing Hermes knowledge to PA...")
    main()
