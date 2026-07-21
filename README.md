# Weblint

Weblint is a snippet and template manager designed to help you organize and reuse code snippets, text templates, and more. It features dynamic variable support, allowing you to create templates that can be filled in on the fly.

## Features

- **Snippet Management**: Create, edit, view, and delete snippets.
- **Dynamic Templating**: Define variables within your snippets to create reusable templates.
- **Variable Types**: Supports single-line inputs, multi-line text areas, dropdown choices, and date/time pickers.
- **Multi-part Snippets**: Group related templates (for example device configs) that share the same variables, with a separate Live Preview and Copy Output per part.
- **Live Preview**: See your filled-in template update in real-time as you enter variables.
- **Multi-Format Support**: Create snippets in Plain Text, Markdown, or HTML.
- **Search**: Quickly find snippets by title or content.
- **Copy to Clipboard**: Easily copy the generated output (Plain Text or Rich Text/HTML).
- **Data Persistence**: Uses a Docker volume to persist your data.

## Variable Syntax

Weblint uses a simple syntax to define variables in your snippets. When you view a snippet, these variables will be presented as form fields.

- **Input (Single Line)**:
  - Syntax: `[[Input=Label|Default]]`
  - Example: `[[Input=Name|John Doe]]`
  - Used for short text fields like names, titles, or short strings.

- **Area (Multi-Line)**:
  - Syntax: `[[Area=Label|Default]]`
  - Example: `[[Area=Description|Enter description here...]]`
  - Used for longer text blocks, notes, or code blocks.

- **Choice (Dropdown)**:
  - Syntax: `[[Choice=?Label|Option1|Option2|Option3]]`
  - Example: `[[Choice=?Status|Pending|In Progress|Completed]]`
  - creates a dropdown menu with the specified options.

- **DateTime**:
  - Syntax: `[[DateTime=Format]]`
  - Example: `[[DateTime=MM-dd-yyyy]]` or `[[DateTime=yyyy-MM-dd HH:mm:ss]]`
  - Automatically inserts the current date/time in the specified format.
  - Supported tokens: `yyyy`, `yy`, `MM`, `M`, `dd`, `d`, `HH`, `H`, `mm`, `ss`.

### Batch Script Mode

In addition to the standard syntax, Weblint supports a "Batch Script" parsing mode. When this mode is selected for a snippet, you can use `%VARIABLE%` syntax to define inputs.

- **Syntax**: `%VARIABLE_NAME%`
- **Example**: `echo "Hello, %USERNAME%!"`
- **Usage**: When viewed, Weblint will generate an input field for `USERNAME`.

## Multi-part Snippets

Use multiple parts when several templates share the same variables but need separate outputs—for example Fortigate, Cisco router, and Cisco switch configs for the same site.

- In the editor, click **+ Add part** to add another named content block.
- Parsing mode and notes are shared for the whole snippet; each part has its own name, content, and type.
- On the view page, fill in variables once. Each part shows its own Live Preview, Raw Source, and Copy Output button.
- Single-part snippets behave exactly as before.

## Getting Started

### Prerequisites

- For Docker (recommended for shared / always-on hosting): [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- For a local single-user install: download a prebuilt desktop binary from [Releases](https://github.com/photoncody/weblint/releases), **or** use Python 3.9+ (see below)

### Desktop app (Windows / Linux / macOS)

Prebuilt standalone binaries are published automatically by GitHub Actions whenever a version tag (`v*.*.*`) is pushed. Download the zip for your platform from the [Releases](https://github.com/photoncody/weblint/releases) page:

| Platform | Artifact |
| --- | --- |
| Windows (x64) | `weblint-windows-x64.zip` |
| Linux (x64) | `weblint-linux-x64.zip` |
| macOS (Apple Silicon) | `weblint-macos-arm64.zip` |

Intel Macs are not covered by CI (GitHub’s macOS runners are Apple Silicon). On Intel macOS, build from source with the `pyinstaller weblint.spec` steps below, or use the Python install.
1. Unzip the archive.
2. Run the `weblint` binary (double-click or from a terminal).
3. Your browser should open to `http://127.0.0.1:5000/`.
4. Snippet data is stored in a `data/` folder next to the binary. Press Ctrl+C in the console to stop.

CI also builds these binaries on every push to `main` and on pull requests (downloadable as workflow artifacts). To publish a new Release yourself:

```bash
git tag v1.2.3
git push origin v1.2.3
```

To build a desktop binary from source locally:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller weblint.spec
# Result: dist/weblint  (or dist/weblint.exe on Windows)
WEBLINT_DESKTOP=1 ./dist/weblint
```

### Installation & Running with Docker (Recommended for servers)

1.  Clone this repository.
2.  Navigate to the project directory.
3.  Run the application using Docker Compose:

    ```bash
    docker-compose up -d
    ```

    This will build the Docker image and start the `weblint` service on port 5000.

4.  Access the application in your browser at: `http://localhost:5000`

### Manual Installation (Python)

If you prefer to run from source without Docker or a prebuilt binary:

1.  Ensure you have Python 3.9+ installed.
2.  Create a virtual environment (optional but recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Run the application (set a secret key, or use desktop mode to auto-generate one):
    ```bash
    # Option A: explicit secret (same as server/Docker)
    SECRET_KEY=$(openssl rand -hex 32) python3 app.py

    # Option B: desktop mode — auto-generates/persists a key under ./data/
    WEBLINT_DESKTOP=1 python3 desktop.py
    ```
5.  Access the application at `http://localhost:5000` (desktop mode opens the browser for you).

## Configuration

### Security

For production use, you should set a strong `SECRET_KEY` environment variable. This key is used by Flask for session management and security.

To generate a secure key, you can run the following command in your terminal (requires OpenSSL):

```bash
openssl rand -hex 32
```

**Using Docker Compose:**

You can create a `.env` file in the project root:

```env
SECRET_KEY=your-super-secret-key-here
```

Or set it when running `docker-compose`:

```bash
SECRET_KEY=your-super-secret-key-here docker-compose up -d
```

### Authentication

Weblint supports optional web-based form authentication. This is disabled by default.

To enable authentication, you must set the following environment variables:

- `WEBLINT_USERNAME`: The username for login.
- `WEBLINT_PASSWORD`: The password for login.

When these variables are present, Weblint will require authentication for all pages except the login page.

**Example (Docker Compose):**

```yaml
    environment:
      - SECRET_KEY=your-super-secret-key-here
      - WEBLINT_USERNAME=admin
      - WEBLINT_PASSWORD=supersecretpassword
```

## Data Persistence

Weblint stores its data in a SQLite database located at `/data/snippets.db` inside the container.
The `docker-compose.yml` defines a volume named `weblint_data` mounted to `/data` to ensure your snippets persist across container restarts.

If you want to access the database file directly on your host machine, you can modify `docker-compose.yml` to use a bind mount:

```yaml
    volumes:
      - ./data:/data
```

When running the desktop binary, data (including an auto-generated `secret.key`) lives in a `data/` folder next to the executable. From source without Docker, data defaults to `./data/` in the working directory.

## JSON Migration

On startup, if the database is empty, Weblint will check for a `/data/snippets.json` file. If found, it will automatically import snippets from this file into the database. This is useful for initial data seeding or migration.
