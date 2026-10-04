import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Добавляем родительский каталог в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard_generator.core.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="YandexGPT to Apache Superset Dashboard Generator")
    parser.add_argument("prompt", type=str, help="Пользовательский запрос на русском языке")
    parser.add_argument("--skip-superset", action="store_true", help="Пропустить вызов Superset REST API")
    parser.add_argument("--bundle-out", type=str, default=None, help="Путь для сохранения сгенерированного bundle.zip")

    args = parser.parse_args()

    result = run_pipeline(
        prompt=args.prompt,
        skip_superset_import=args.skip_superset,
        progress_callback=lambda msg: print(f"[{msg.split()[0]}] {' '.join(msg.split()[1:])}"),
    )

    if result.success:
        print("\n" + "=" * 60)
        print(f"✅ ДАШБОРД УСПЕШНО СОЗДАН: «{result.dashboard_title}»")
        print(f"🔗 ССЫЛКА В SUPERSET: {result.dashboard_url}")
        print(f"🆔 UUID: {result.dashboard_uuid}")
        print(f"📊 ЧАРТОВ: {len(result.plan.charts) if result.plan else 0}")
        print("=" * 60)

        if args.bundle_out and result.bundle_bytes:
            with open(args.bundle_out, "wb") as f:
                f.write(result.bundle_bytes)
            print(f"💾 Бандл сохранен в: {args.bundle_out}")
    else:
        print("\n" + "=" * 60)
        print("❌ ОШИБКА ПОСТРОЕНИЯ ДАШБОРДА:")
        print(result.error_message)
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
