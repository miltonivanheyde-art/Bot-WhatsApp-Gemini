import argparse
import sys
import os
import getpass
from datetime import datetime, timezone

# Añadir el directorio raíz al path para poder importar desde 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import DatabaseManager

DEFAULT_DB_PATH = "data/tita.db"

def handle_list(args):
    """Lista las versiones de conocimiento con estado PENDING."""
    db = DatabaseManager(args.db_path)
    try:
        db.connect()
        # NOTA: Se usa un método no público por ausencia de API pública para esta funcionalidad.
        cursor = db._execute_read_query("SELECT id, final_url, retrieval_date, mime_type, content_hash FROM knowledge_versions WHERE current_status = 'PENDING'")
        versions = cursor.fetchall()
        if not versions:
            print("No hay versiones pendientes de validación.")
            return

        print("=" * 80)
        print(f"{'ID':<5} | {'URL Final':<40} | {'Fecha':<20} | {'Hash (corto)':<12}")
        print("-" * 80)
        for version in versions:
            hash_corto = version['content_hash'][:10]
            fecha_corta = version['retrieval_date'][:19].replace("T", " ")
            url_corta = version['final_url'][:38] + "..." if len(version['final_url']) > 40 else version['final_url']
            print(f"{version['id']:<5} | {url_corta:<40} | {fecha_corta:<20} | {hash_corto:<12}")
        print("=" * 80)

    except Exception as e:
        print(f"Error al listar versiones pendientes: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

def handle_show(args):
    """Muestra los detalles de una versión de conocimiento específica."""
    db = DatabaseManager(args.db_path)
    try:
        db.connect()
        version = db.get_knowledge_version_by_id(args.version_id)
        if not version:
            print(f"Error: No se encontró la versión con ID {args.version_id}", file=sys.stderr)
            sys.exit(1)

        print("=" * 80)
        print(f"Detalles de la Versión ID: {version['id']}")
        print("-" * 80)
        print(f"  Estado Actual:     {version['current_status']}")
        print(f"  URL Final:         {version['final_url']}")
        print(f"  Fecha Recuperación: {version['retrieval_date']}")
        print(f"  Tipo MIME:         {version['mime_type']}")
        print(f"  Hash Contenido:    {version['content_hash']}")
        
        if version['extracted_text']:
            print("\n--- Texto Extraído ---")
            print(version['extracted_text'])
            print("----------------------\n")

        if version['original_content']:
            preview = version['original_content'][:500]
            print("\n--- Vista Previa del Contenido (primeros 500 bytes) ---")
            try:
                print(preview.decode('utf-8', errors='ignore'))
            except:
                print(preview)
            print("-----------------------------------------------------\n")

    except Exception as e:
        print(f"Error al mostrar la versión {args.version_id}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

def handle_validate(args):
    """Valida una versión PENDING y crea una entrada de conocimiento."""
    db = DatabaseManager(args.db_path)
    try:
        db.connect()
        version = db.get_knowledge_version_by_id(args.version_id)
        if not version:
            raise ValueError(f"No se encontró la versión con ID {args.version_id}")
        if version['current_status'] != 'PENDING':
            raise ValueError(f"Solo se pueden validar versiones en estado PENDING. Estado actual: {version['current_status']}")

        # 1. Actualizar el estado de la versión
        db.update_knowledge_version_status(
            version_id=args.version_id,
            new_status='VALIDATED',
            event_by=getpass.getuser(),
            event_date=datetime.now(timezone.utc).isoformat(),
            notes=args.notes
        )

        # 2. Crear la entrada de conocimiento
        db.insert_knowledge_entry(
            title=args.title,
            keywords=args.keywords,
            description=args.description,
            active_version_id=args.version_id
        )
        print(f"✅ Versión {args.version_id} validada y entrada de conocimiento creada con título '{args.title}'.")

    except Exception as e:
        print(f"Error al validar la versión {args.version_id}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

def handle_reject(args):
    """Rechaza una versión PENDING."""
    db = DatabaseManager(args.db_path)
    try:
        db.connect()
        version = db.get_knowledge_version_by_id(args.version_id)
        if not version:
            raise ValueError(f"No se encontró la versión con ID {args.version_id}")
        if version['current_status'] != 'PENDING':
            raise ValueError(f"Solo se pueden rechazar versiones en estado PENDING. Estado actual: {version['current_status']}")

        db.update_knowledge_version_status(
            version_id=args.version_id,
            new_status='REJECTED',
            event_by=getpass.getuser(),
            event_date=datetime.now(timezone.utc).isoformat(),
            notes=args.notes
        )
        print(f"✅ Versión {args.version_id} rechazada.")

    except Exception as e:
        print(f"Error al rechazar la versión {args.version_id}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

def handle_delete_test(args):
    """Comando de borrado para contenido de prueba (no implementado en la capa de DB)."""
    print("Error: La funcionalidad de borrado no está implementada en la API de la base de datos.", file=sys.stderr)
    print("Esta es una medida de seguridad para prevenir borrados accidentales.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Herramienta de línea de comandos para gestionar la base de conocimiento.")
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help=f"Ruta al archivo de la base de datos SQLite (por defecto: {DEFAULT_DB_PATH})")
    
    subparsers = parser.add_subparsers(dest='command', required=True, help='Comando a ejecutar')

    # Comando: list
    parser_list = subparsers.add_parser('list', help='Lista las versiones pendientes de validación.')
    parser_list.set_defaults(func=handle_list)

    # Comando: show
    parser_show = subparsers.add_parser('show', help='Muestra los detalles de una versión específica.')
    parser_show.add_argument('version_id', type=int, help='ID de la versión de conocimiento a mostrar.')
    parser_show.set_defaults(func=handle_show)

    # Comando: validate
    parser_validate = subparsers.add_parser('validate', help='Valida una versión PENDING y crea una entrada de conocimiento.')
    parser_validate.add_argument('version_id', type=int, help='ID de la versión a validar.')
    parser_validate.add_argument('--title', required=True, help='Título para la nueva entrada de conocimiento.')
    parser_validate.add_argument('--keywords', help='Palabras clave separadas por comas.')
    parser_validate.add_argument('--description', help='Descripción breve de la entrada de conocimiento.')
    parser_validate.add_argument('--notes', help='Notas opcionales para el log de validación.')
    parser_validate.set_defaults(func=handle_validate)

    # Comando: reject
    parser_reject = subparsers.add_parser('reject', help='Rechaza una versión PENDING.')
    parser_reject.add_argument('version_id', type=int, help='ID de la versión a rechazar.')
    parser_reject.add_argument('--notes', required=True, help='Motivo del rechazo (obligatorio).')
    parser_reject.set_defaults(func=handle_reject)

    # Comando: delete-test
    parser_delete = subparsers.add_parser('delete-test', help='(No funcional) Borra una versión de prueba.')
    parser_delete.add_argument('version_id', type=int, help='ID de la versión de prueba a borrar.')
    parser_delete.set_defaults(func=handle_delete_test)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()