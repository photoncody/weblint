# Weblint

Weblint is a snippet and template manager designed to help you organize and reuse code snippets, text templates, and more. It features dynamic variable support, allowing you to create templates that can be filled in on the fly.

## Features

- **Snippet Management**: Create, edit, view, and delete snippets.
- **Dynamic Templating**: Define variables within your snippets to create reusable templates.
- **Variable Types**: Supports single-line inputs, multi-line text areas, dropdown choices, and date/time pickers.
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

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your machine.

### Installation & Running (Recommended)

1.  Clone this repository.
2.  Navigate to the project directory.
3.  Run the application using Docker Compose:

    ```bash
    docker-compose up -d
    ```

    This will build the Docker image and start the `weblint` service on port 5000.

4.  Access the application in your browser at: `http://localhost:5000`

### Manual Installation (Python)

If you prefer to run it without Docker:

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
4.  Run the application:
    ```bash
    python3 app.py
    ```
5.  Access the application at `http://localhost:5000`.

## Configuration

### Security

For production use, you should set a strong `SECRET_KEY` environment variable. This key is used by Flask for session management and security.

To generate a secure key, you can run the following command in your terminal:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
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

## Data Persistence

Weblint stores its data in a SQLite database located at `/data/snippets.db` inside the container.
The `docker-compose.yml` defines a volume named `weblint_data` mounted to `/data` to ensure your snippets persist across container restarts.

If you want to access the database file directly on your host machine, you can modify `docker-compose.yml` to use a bind mount:

```yaml
    volumes:
      - ./data:/data
```

## JSON Migration

On startup, if the database is empty, Weblint will check for a `/data/snippets.json` file. If found, it will automatically import snippets from this file into the database. This is useful for initial data seeding or migration.
