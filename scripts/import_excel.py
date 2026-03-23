#!/usr/bin/env python3
"""
scripts/import_excel.py
-----------------------
Excel 批量导入命令行工具。

用法：
    python scripts/import_excel.py --file data/relations.xlsx
    python scripts/import_excel.py --file data/relations.xlsx --dry-run
    python scripts/import_excel.py --file data/relations.xlsx --sheet "告警关系"

Excel 格式要求（支持中英文列名）：
    | source_node_id | source_node_type | target_node_id | target_node_type | relation_type | confidence | provenance |
    | CNC-M1         | Device           | ALM-001        | Alarm            | DEVICE__TRIGGERS__ALARM | 0.85 | mes_structured |

详见 docs/data-model.md §Excel 导入规范。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from relos.ingestion.excel_importer import ExcelImporter


async def _write_to_neo4j(
    relations: list,  # list[RelationObject]
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> tuple[int, int]:
    """将解析好的关系批量写入 Neo4j，返回 (success, failed)。"""
    from neo4j import AsyncGraphDatabase

    from relos.core.models import Node
    from relos.core.repository import RelationRepository

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    await driver.verify_connectivity()
    repo = RelationRepository(driver)

    success = 0
    failed = 0

    for rel in relations:
        try:
            # 确保节点存在（MERGE）
            await repo.upsert_node(Node(
                id=rel.source_node_id,
                node_type=rel.source_node_type,
                name=rel.source_node_id,
            ))
            await repo.upsert_node(Node(
                id=rel.target_node_id,
                node_type=rel.target_node_type,
                name=rel.target_node_id,
            ))
            await repo.upsert_relation(rel)
            success += 1
        except Exception as exc:
            print(f"  [ERROR] 写入关系 {rel.id} 失败: {exc}", file=sys.stderr)
            failed += 1

    await driver.close()
    return success, failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RelOS Excel 批量导入工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", "-f", required=True, help="Excel 文件路径（.xlsx）")
    parser.add_argument("--sheet", "-s", default=0, help="工作表名称或索引（默认第一张）")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只解析验证，不写入数据库"
    )
    parser.add_argument(
        "--output-json", "-o",
        help="将导入结果汇总保存为 JSON 文件（可选）"
    )
    parser.add_argument("--neo4j-uri",    default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user",   default="neo4j")
    parser.add_argument("--neo4j-pass",   default="relos_dev")
    parser.add_argument(
        "--default-confidence", type=float, default=0.75,
        help="无 confidence 列时的默认置信度（默认 0.75）"
    )
    parser.add_argument(
        "--min-accuracy", type=float, default=0.95,
        help="最低成功率要求（默认 0.95），低于此值时退出码为 1"
    )
    args = parser.parse_args()

    # ── 解析 Excel ──────────────────────────────────────────────────
    print(f"📂 正在解析: {args.file}")
    importer = ExcelImporter(default_confidence=args.default_confidence)

    try:
        sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        result = importer.parse_file(args.file, sheet_name=sheet)
    except ImportError as exc:
        print(f"❌ 缺少依赖: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"❌ 文件解析失败: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── 打印解析结果 ─────────────────────────────────────────────────
    print(f"\n📊 解析结果：")
    print(f"   总行数:   {result.total_rows}")
    print(f"   成功:     {result.success_count}")
    print(f"   失败:     {result.failed_count}")
    print(f"   准确率:   {result.accuracy * 100:.1f}%")

    if result.errors:
        print(f"\n⚠️  解析错误（前 10 条）：")
        for err in result.errors[:10]:
            print(f"   行 {err.row_number}: {err.error}")

    # ── 写入 Neo4j（非 dry-run）────────────────────────────────────
    neo4j_success = 0
    neo4j_failed = 0
    if not args.dry_run and result.relations:
        print(f"\n⬆️  写入 Neo4j ({args.neo4j_uri})...")
        neo4j_success, neo4j_failed = asyncio.run(_write_to_neo4j(
            result.relations,
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_pass,
        ))
        print(f"   写入成功: {neo4j_success}，失败: {neo4j_failed}")
    elif args.dry_run:
        print("\n🔍 Dry-run 模式：跳过写入 Neo4j")

    # ── 保存 JSON 汇总 ───────────────────────────────────────────────
    if args.output_json:
        summary = result.summary()
        summary["neo4j_write_success"] = neo4j_success
        summary["neo4j_write_failed"] = neo4j_failed
        Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\n💾 结果已保存: {args.output_json}")

    # ── 检查准确率门槛 ───────────────────────────────────────────────
    if result.total_rows > 0 and result.accuracy < args.min_accuracy:
        print(
            f"\n❌ 准确率 {result.accuracy * 100:.1f}% 低于要求的 "
            f"{args.min_accuracy * 100:.1f}%，退出码 1",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n✅ 导入完成")


if __name__ == "__main__":
    main()
