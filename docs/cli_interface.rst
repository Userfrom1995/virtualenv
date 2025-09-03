CLI interface
=============

.. _cli_flags:

CLI flags
~~~~~~~~~

``virtualenv`` is primarily a command line application.

It modifies the environment variables in a shell to create an isolated Python environment, so you'll need to have a
shell to run it. You can type in ``virtualenv`` (name of the application) followed by flags that control its
behavior. All options have sensible defaults, and there's one required argument: the name/path of the virtual
environment to create. The default values for the command line options can be overridden via the
:ref:`conf_file` or :ref:`env_vars`. Environment variables takes priority over the configuration file values
(``--help`` will show if a default comes from the environment variable as the help message will end in this case
with environment variables or the configuration file).

The options that can be passed to virtualenv, along with their default values and a short description are listed below.

:command:`virtualenv [OPTIONS]`

.. table_cli::
   :module: virtualenv.run
   :func: build_parser_only

Discovery options
~~~~~~~~~~~~~~~~~

Understanding Interpreter Discovery: ``--python`` vs. ``--try-first-with``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can control which Python interpreter ``virtualenv`` selects using the ``--python`` and ``--try-first-with`` flags.
To avoid confusion, it's best to think of them as the "rule" and the "hint".

**``--python <spec>``: The Rule**

This flag sets the mandatory requirements for the interpreter. The ``<spec>`` can be:

- **A version string** (e.g., ``python3.8``, ``pypy3``). ``virtualenv`` will search for any interpreter that matches this version.
- **An absolute path** (e.g., ``/usr/bin/python3.8``). This is a *strict* requirement. Only the interpreter at this exact path will be used. If it does not exist or is not a valid interpreter, creation will fail.

**``--try-first-with <path>``: The Hint**

This flag provides a path to a Python executable to check *before* ``virtualenv`` performs its standard search. This can speed up discovery or help select a specific interpreter when multiple versions exist on your system.

**How They Work Together**

``virtualenv`` will only use an interpreter from ``--try-first-with`` if it **satisfies the rule** from the ``--python`` flag. The ``--python`` rule always wins.

**Examples:**

1. **Hint does not match the rule:**

   .. code-block:: bash

      virtualenv --python python3.8 --try-first-with /usr/bin/python3.10 my-env

   - **Result:** ``virtualenv`` first inspects ``/usr/bin/python3.10``. It sees this does not match the ``python3.8`` rule and **rejects it**. It then proceeds with its normal search to find a ``python3.8`` interpreter elsewhere.

2. **Hint does not match a strict path rule:**

   .. code-block:: bash

      virtualenv --python /usr/bin/python3.8 --try-first-with /usr/bin/python3.10 my-env

   - **Result:** The rule is strictly ``/usr/bin/python3.8``. ``virtualenv`` checks the ``/usr/bin/python3.10`` hint, sees the path doesn't match, and **rejects it**. It then moves on to test ``/usr/bin/python3.8`` and successfully creates the environment.

This approach ensures that the behavior is predictable and that ``--python`` remains the definitive source of truth for the user's intent.


Defaults
~~~~~~~~

.. _conf_file:

Configuration file
^^^^^^^^^^^^^^^^^^

Unless ``VIRTUALENV_CONFIG_FILE`` is set, virtualenv looks for a standard ``virtualenv.ini`` configuration file.
The exact location depends on the operating system you're using, as determined by :pypi:`platformdirs` application
configuration definition. It can be overridden by setting the ``VIRTUALENV_CONFIG_FILE`` environment variable.
The configuration file location is printed as at the end of the output when ``--help`` is passed.

The keys of the settings are derived from the command line option (left strip the ``-`` characters, and replace ``-``
with ``_``). Where multiple flags are available first found wins (where order is as it shows up under the ``--help``).

For example, :option:`--python <python>` would be specified as:

.. code-block:: ini

  [virtualenv]
  python = /opt/python-3.8/bin/python

Options that take multiple values, like :option:`extra-search-dir` can be specified as:

.. code-block:: ini

  [virtualenv]
  extra_search_dir =
      /path/to/dists
      /path/to/other/dists

.. _env_vars:

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

Default values may be also specified via environment variables. The keys of the settings are derived from the
command line option (left strip the ``-`` characters, and replace ``-`` with ``_``, finally capitalize the name). Where
multiple flags are available first found wins (where order is as it shows up under the ``--help``).

For example, to use a custom Python binary, instead of the one virtualenv is run with, you can set the environment
variable ``VIRTUALENV_PYTHON`` like:

.. code-block:: console

   env VIRTUALENV_PYTHON=/opt/python-3.8/bin/python virtualenv

Where the option accepts multiple values, for example for :option:`python` or
:option:`extra-search-dir`, the values can be separated either by literal
newlines or commas. Newlines and commas can not be mixed and if both are
present only the newline is used for separating values. Examples for multiple
values:


.. code-block:: console

   env VIRTUALENV_PYTHON=/opt/python-3.8/bin/python,python3.8 virtualenv
   env VIRTUALENV_EXTRA_SEARCH_DIR=/path/to/dists\n/path/to/other/dists virtualenv

The equivalent CLI-flags based invocation for the above examples would be:

.. code-block:: console

   virtualenv --python=/opt/python-3.8/bin/python --python=python3.8
   virtualenv --extra-search-dir=/path/to/dists --extra-search-dir=/path/to/other/dists


.. _envon_cli:

envon - Virtual Environment Activator
======================================

``envon`` is a companion CLI tool that simplifies virtual environment activation across different shells.
Instead of remembering different activation commands for different shells and platforms, ``envon`` provides
a unified interface to locate and activate virtual environments.

Basic Usage
~~~~~~~~~~~

Find and activate the nearest virtual environment:

.. code-block:: console

   $ envon
   . '/path/to/project/.venv/bin/activate'

The command outputs the appropriate activation command for your current shell. To actually activate the environment,
you need to evaluate the output:

.. code-block:: console

   $ eval "$(envon)"

Or use the shell-specific bootstrap function (recommended - see :ref:`envon_bootstrap`).

Command Options
~~~~~~~~~~~~~~~

.. code-block:: console

   envon [target] [options]

**Arguments:**

* ``target`` (optional): Path to virtual environment, project directory, or environment name in ``WORKON_HOME``

**Options:**

* ``--emit SHELL``: Force output format for specific shell (bash, fish, powershell, cmd, etc.)
* ``--print-path``: Print the resolved virtual environment path instead of activation command
* ``--bootstrap SHELL``: Generate shell wrapper function for direct activation

Examples
~~~~~~~~

**Basic usage - find nearest environment:**

.. code-block:: console

   $ envon
   . '/home/user/myproject/.venv/bin/activate'

**Specify a target:**

.. code-block:: console

   $ envon /path/to/my/venv
   . '/path/to/my/venv/bin/activate'

   $ envon myproject-env  # looks in $WORKON_HOME
   . '/home/user/.virtualenvs/myproject-env/bin/activate'

**Force shell format:**

.. code-block:: console

   $ envon --emit fish
   source '/home/user/myproject/.venv/bin/activate.fish'

   $ envon --emit powershell
   . '/home/user/myproject/.venv/Scripts/Activate.ps1'

**Get environment path only:**

.. code-block:: console

   $ envon --print-path
   /home/user/myproject/.venv

Virtual Environment Discovery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``envon`` uses intelligent discovery to find virtual environments:

1. **No target specified:**

   - First checks current directory for common names: ``.venv``, ``venv``, ``env``, ``.env``
   - If multiple found, prompts for selection (in interactive mode)
   - Falls back to searching parent directories

2. **Target specified:**

   - If it's a path to a virtual environment, uses it directly
   - If it's a directory containing virtual environments, lists and selects
   - If it's a name, searches in ``$WORKON_HOME``

3. **Detection criteria:**

   - Presence of ``pyvenv.cfg`` file (most reliable)
   - Existence of activation scripts (``bin/activate``, ``Scripts/activate.bat``, etc.)

.. _envon_bootstrap:

Shell Integration (Bootstrap)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For the best experience, add ``envon`` wrapper functions to your shell configuration.
These allow ``envon`` to directly activate environments instead of just printing commands.

**Bash/Zsh (.bashrc, .zshrc):**

.. code-block:: bash

   # Add this to your .bashrc or .zshrc
   eval "$(envon --bootstrap bash)"

   # Or manually add the function:
   envon() {
     local cmd;
     cmd="$(command envon --emit bash "$@")" || { echo "$cmd" >&2; return 1; };
     eval "$cmd";
   }

**Fish (~/.config/fish/config.fish):**

.. code-block:: fish

   # Add this to your config.fish
   envon --bootstrap fish | source

   # Or manually add the function:
   function envon
       set cmd (command envon --emit fish $argv)
       if test $status -ne 0
           echo $cmd >&2
           return 1
       end
       eval $cmd
   end

**PowerShell ($PROFILE):**

.. code-block:: powershell

   # Add this to your PowerShell profile
   Invoke-Expression (envon --bootstrap powershell)

   # Or manually add the function:
   function envon {
     param([Parameter(Position=0)][string]$Target)
     $argsList = @(); if ($Target) { $argsList += $Target }
     $envonExe = Get-Command envon -CommandType Application -ErrorAction SilentlyContinue
     if (-not $envonExe) { Write-Error 'envon console script not found on PATH'; return }
     $cmd = & $envonExe.Source --emit powershell @argsList
     if ($LASTEXITCODE -ne 0) { Write-Error $cmd; return }
     Invoke-Expression $cmd
   }

**Nushell (~/.config/nushell/config.nu):**

.. code-block:: shell

   # Add this to your config.nu
   source (envon --bootstrap nushell | str trim)

   # Or manually add the function:
   def-env envon [...args] {
     let cmd = (^envon --emit nushell ...$args)
     overlay use $cmd
   }

**C Shell (.cshrc):**

.. code-block:: csh

   # Add this to your .cshrc
   eval "`envon --bootstrap csh`"

   # Or manually add the alias:
   alias envon 'set _ev=`envon --emit csh \!*` && eval $_ev && unset _ev'

Shell Support
~~~~~~~~~~~~~

``envon`` supports activation for all shells that virtualenv supports:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Shell
     - Platform
     - Activation Command Generated
   * - Bash/Zsh/Sh
     - POSIX
     - ``. 'path/to/activate'``
   * - Fish
     - POSIX
     - ``source 'path/to/activate.fish'``
   * - C Shell (csh/tcsh)
     - POSIX
     - ``source 'path/to/activate.csh'``
   * - Nushell
     - Cross-platform
     - ``overlay use 'path/to/activate.nu'``
   * - PowerShell
     - Windows/Cross-platform
     - ``. 'path/to/Activate.ps1'``
   * - CMD/Batch
     - Windows
     - ``call "path/to/activate.bat"``

Integration with virtualenvwrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``envon`` is compatible with ``virtualenvwrapper`` environments. Set the ``WORKON_HOME`` environment variable,
and ``envon`` will search for environments by name:

.. code-block:: console

   $ export WORKON_HOME="$HOME/.virtualenvs"
   $ envon myproject
   . '/home/user/.virtualenvs/myproject/bin/activate'
