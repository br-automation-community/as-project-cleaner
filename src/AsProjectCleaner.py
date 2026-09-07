import os
import sys
import stat
import shutil
import threading
import tkinter as tk

from pathlib import Path
from tkinter import filedialog, messagebox, ttk


# --------------------------------------------------
# Configuration
# --------------------------------------------------

# Generated Automation Studio folders that may be deleted.
FOLDERS_TO_DELETE = {
    "Temp",
    "Binaries",
    "Diagnosis",
}


# --------------------------------------------------
# Resource path helper
# --------------------------------------------------

def resource_path(relative_path):
    """
    Return the correct path to a resource.

    Works both:
    - when running from source
    - when running as a PyInstaller executable
    """

    if hasattr(sys, "_MEIPASS"):
        # PyInstaller temporary folder
        base_path = sys._MEIPASS

    else:
        # Project root = one folder above /src
        base_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    return os.path.join(base_path, relative_path)


# --------------------------------------------------
# Find Automation Studio projects
# --------------------------------------------------

def find_as_projects(root_folder):
    """
    Recursively search through root_folder.

    Any directory containing at least one .apj file
    is considered an Automation Studio project.

    Returns:
        List of Path objects.
    """

    projects = []

    for current_dir, dirnames, filenames in os.walk(root_folder):

        # Check whether the current directory contains
        # an .apj file.
        #
        # .lower() makes the test case-insensitive.
        has_apj = any(
            filename.lower().endswith(".apj")
            for filename in filenames
        )

        if has_apj:
            projects.append(Path(current_dir))

    return projects


# --------------------------------------------------
# Find generated folders
# --------------------------------------------------

def get_cleanup_targets(project_folders):
    """
    Look for Temp, Binaries and Diagnosis folders
    directly inside each Automation Studio project.

    Returns:
        List of Path objects.
    """

    targets = []

    for project in project_folders:

        for folder_name in FOLDERS_TO_DELETE:

            folder = project / folder_name

            # Only add the folder if it exists.
            if folder.is_dir():
                targets.append(folder)

    return targets


# --------------------------------------------------
# Handle read-only files
# --------------------------------------------------

def remove_readonly(func, path, exc):
    """
    Called by shutil.rmtree() when Windows refuses
    to remove a file.

    This can happen when files are marked read-only.

    The function:
    1. Makes the file writable.
    2. Retries the original delete operation.
    """

    os.chmod(
        path,
        stat.S_IWRITE
    )

    func(path)


# --------------------------------------------------
# Delete one folder
# --------------------------------------------------

def delete_folder(folder):
    """
    Delete one folder and everything inside it.

    Returns:
        None when successful.
        Exception object when deletion fails.
    """

    try:

        shutil.rmtree(
            folder,
            onexc=remove_readonly
        )

        return None

    except Exception as exc:

        return exc


# --------------------------------------------------
# GUI busy / ready state
# --------------------------------------------------

def set_gui_busy(busy):
    """
    Disable GUI controls while a scan or cleanup
    operation is running.
    """

    if busy:

        browse_button.config(
            state="disabled"
        )

        cleanup_button.config(
            state="disabled"
        )

        path_entry.config(
            state="disabled"
        )

    else:

        browse_button.config(
            state="normal"
        )

        cleanup_button.config(
            state="normal"
        )

        path_entry.config(
            state="normal"
        )


# --------------------------------------------------
# Show progress bar
# --------------------------------------------------

def show_progress_bar():
    """
    Display the progress bar.

    It is hidden when the application starts and
    only appears when Scan and Clean is pressed.
    """

    # pack_forget() is used when we want to hide it.
    # Calling pack() again makes it visible.
    progress_bar.pack(
        fill="x",
        padx=40,
        pady=(0, 8)
    )


# --------------------------------------------------
# Hide progress bar
# --------------------------------------------------

def hide_progress_bar():
    """
    Hide the progress bar.
    """

    progress_bar.stop()

    progress_bar.pack_forget()


# --------------------------------------------------
# Browse for root folder
# --------------------------------------------------

def browse_folder():
    """
    Open a Windows folder selection dialog.
    """

    folder = filedialog.askdirectory(
        title="Select folder containing Automation Studio projects"
    )

    if folder:

        folder_var.set(folder)


# --------------------------------------------------
# Start scan
# --------------------------------------------------

def start_cleanup():
    """
    Validate the selected path and start scanning.

    The actual scan runs in a background thread so
    that the GUI remains responsive.
    """

    root_folder = folder_var.get().strip()


    # --------------------------------------------------
    # Validate selected folder
    # --------------------------------------------------

    if not root_folder:

        messagebox.showwarning(
            "No folder selected",
            "Please select a folder first."
        )

        return


    root_path = Path(root_folder)


    if not root_path.is_dir():

        messagebox.showerror(
            "Invalid folder",
            "The selected path does not exist or is not a folder."
        )

        return


    # --------------------------------------------------
    # Prepare GUI
    # --------------------------------------------------

    set_gui_busy(True)

    status_var.set(
        "Scanning for Automation Studio projects..."
    )


    # Show progress bar only after Scan and Clean
    # has been pressed.
    show_progress_bar()


    # During scanning we don't know how many folders
    # will be found yet, so use indeterminate mode.
    progress_bar.config(
        mode="indeterminate"
    )

    progress_bar.start(10)


    # --------------------------------------------------
    # Run scan in background
    # --------------------------------------------------

    scan_thread = threading.Thread(
        target=scan_worker,
        args=(root_path,),
        daemon=True
    )

    scan_thread.start()


# --------------------------------------------------
# Background scan
# --------------------------------------------------

def scan_worker(root_path):
    """
    Scan the selected root folder.

    This function runs in a background thread.
    """

    projects = find_as_projects(
        root_path
    )

    targets = get_cleanup_targets(
        projects
    )


    # Tkinter GUI operations must happen
    # in the main thread.
    root.after(
        0,
        scan_finished,
        projects,
        targets
    )


# --------------------------------------------------
# Scan finished
# --------------------------------------------------

def scan_finished(projects, targets):
    """
    Handle the result of the background scan.
    """

    progress_bar.stop()

    progress_bar.config(
        mode="determinate",
        value=0
    )


    # --------------------------------------------------
    # No projects found
    # --------------------------------------------------

    if not projects:

        set_gui_busy(False)

        hide_progress_bar()

        status_var.set(
            "Ready"
        )

        messagebox.showinfo(
            "No projects found",
            "No Automation Studio projects (.apj files) were found."
        )

        return


    # --------------------------------------------------
    # Projects found but nothing to delete
    # --------------------------------------------------

    if not targets:

        set_gui_busy(False)

        hide_progress_bar()

        status_var.set(
            "Ready"
        )

        messagebox.showinfo(
            "Nothing to clean",
            (
                f"Found {len(projects)} Automation Studio project(s).\n\n"
                f"No Temp, Binaries or Diagnosis folders were found."
            )
        )

        return


    # --------------------------------------------------
    # Build preview
    # --------------------------------------------------

    preview_limit = 20

    preview = "\n".join(
        str(folder)
        for folder in targets[:preview_limit]
    )


    if len(targets) > preview_limit:

        preview += (
            f"\n\n...and "
            f"{len(targets) - preview_limit} more."
        )


    # --------------------------------------------------
    # Ask for confirmation
    # --------------------------------------------------

    confirmed = messagebox.askyesno(
        "Confirm cleanup",
        (
            f"Automation Studio projects found: "
            f"{len(projects)}\n\n"

            f"Generated folders found: "
            f"{len(targets)}\n\n"

            f"The following folders will be "
            f"permanently deleted:\n\n"

            f"{preview}\n\n"

            f"Continue?"
        )
    )


    # --------------------------------------------------
    # User cancelled
    # --------------------------------------------------

    if not confirmed:

        set_gui_busy(False)

        hide_progress_bar()

        status_var.set(
            "Ready"
        )

        return


    # --------------------------------------------------
    # Prepare deletion progress
    # --------------------------------------------------

    progress_bar.config(
        mode="determinate",
        maximum=len(targets),
        value=0
    )


    status_var.set(
        "Deleting generated folders..."
    )


    # --------------------------------------------------
    # Start background deletion
    # --------------------------------------------------

    delete_thread = threading.Thread(
        target=delete_worker,
        args=(projects, targets),
        daemon=True
    )

    delete_thread.start()


# --------------------------------------------------
# Background deletion
# --------------------------------------------------

def delete_worker(projects, targets):
    """
    Delete all target folders.

    Runs in a background thread so the application
    does not become "Not Responding".
    """

    deleted = []
    failed = []

    total = len(targets)


    for index, folder in enumerate(
        targets,
        start=1
    ):

        error = delete_folder(
            folder
        )


        if error is None:

            deleted.append(
                folder
            )

        else:

            failed.append(
                (folder, error)
            )


        # --------------------------------------------------
        # Update progress safely
        # --------------------------------------------------

        root.after(
            0,
            update_progress,
            index,
            total,
            folder
        )


    # --------------------------------------------------
    # Cleanup complete
    # --------------------------------------------------

    root.after(
        0,
        cleanup_finished,
        projects,
        targets,
        deleted,
        failed
    )


# --------------------------------------------------
# Update progress bar
# --------------------------------------------------

def update_progress(current, total, folder):
    """
    Update the progress bar and status label.
    """

    progress_bar["value"] = current


    status_var.set(
        f"Deleting {current} of {total}: {folder.name}"
    )


# --------------------------------------------------
# Format errors
# --------------------------------------------------

def format_error(folder, error):
    """
    Convert common Windows deletion errors into
    more helpful messages.
    """

    if isinstance(
        error,
        PermissionError
    ):

        return (
            f"{folder}\n"
            f"Access denied.\n\n"

            f"A file may be read-only, locked, "
            f"or currently being used by another "
            f"application.\n\n"

            f"Close Automation Studio and other "
            f"programs using this project and "
            f"try again."
        )


    return (
        f"{folder}\n"
        f"{error}"
    )


# --------------------------------------------------
# Cleanup finished
# --------------------------------------------------

def cleanup_finished(
        projects,
        targets,
        deleted,
        failed
):
    """
    Display the final cleanup summary.
    """

    set_gui_busy(False)


    # Hide the progress bar again once cleanup is finished.
    hide_progress_bar()


    status_var.set(
        "Cleanup complete"
    )


    # --------------------------------------------------
    # Build summary
    # --------------------------------------------------

    result = (
        f"Cleanup complete.\n\n"
        f"Projects found: {len(projects)}\n"
        f"Folders found: {len(targets)}\n"
        f"Folders deleted: {len(deleted)}\n"
        f"Failures: {len(failed)}"
    )


    # --------------------------------------------------
    # Add errors if necessary
    # --------------------------------------------------

    if failed:

        result += (
            "\n\nFailed folders:\n\n"
        )


        max_errors_to_show = 5


        for folder, error in failed[:max_errors_to_show]:

            result += format_error(
                folder,
                error
            )

            result += (
                "\n\n"
                "--------------------"
                "\n\n"
            )


        if len(failed) > max_errors_to_show:

            result += (
                f"...and "
                f"{len(failed) - max_errors_to_show} "
                f"more failure(s)."
            )


    # --------------------------------------------------
    # Show final message
    # --------------------------------------------------

    if failed:

        messagebox.showwarning(
            "Cleanup complete with errors",
            result
        )

    else:

        messagebox.showinfo(
            "Cleanup complete",
            result
        )


# ==================================================
# MAIN GUI
# ==================================================


# --------------------------------------------------
# Main application window
# --------------------------------------------------

root = tk.Tk()


root.title(
    "Automation Studio Project Cleaner"
)


# --------------------------------------------------
# Custom icon
# --------------------------------------------------

try:

    root.iconbitmap(
        resource_path(os.path.join("assets", "ASImage.ico"))
    )

except Exception as exc:

    # The application should still work even
    # if the icon cannot be loaded.
    print(
        f"Could not load icon: {exc}"
    )


# --------------------------------------------------
# Window configuration
# --------------------------------------------------

root.geometry(
    "800x230"
)

root.minsize(
    650,
    230
)

root.resizable(
    True,
    False
)


# --------------------------------------------------
# GUI variables
# --------------------------------------------------

folder_var = tk.StringVar()


status_var = tk.StringVar(
    value="Ready"
)


# --------------------------------------------------
# ttk style
# --------------------------------------------------

style = ttk.Style(
    root
)


# The clam theme allows custom progress bar
# colors on Windows.
style.theme_use(
    "clam"
)


# --------------------------------------------------
# Orange progress bar style
# --------------------------------------------------

style.configure(
    "Orange.Horizontal.TProgressbar",

    # Empty background of the progress bar.
    troughcolor="#E6E6E6",

    # Main progress color.
    background="#FF9F03",

    # Border and shading colors.
    bordercolor="#E6E6E6",
    lightcolor="#FF9F03",
    darkcolor="#FF9F03"
)


# --------------------------------------------------
# Application title
# --------------------------------------------------

title_label = tk.Label(
    root,

    text=(
        "Automation Studio Project Cleaner"
    ),

    font=(
        "Segoe UI",
        14,
        "bold"
    )
)


title_label.pack(
    pady=(15, 10)
)


# --------------------------------------------------
# Folder selection row
# --------------------------------------------------

path_frame = tk.Frame(
    root
)


path_frame.pack(
    fill="x",
    padx=15
)


# --------------------------------------------------
# Folder path field
# --------------------------------------------------

path_entry = tk.Entry(
    path_frame,

    textvariable=folder_var,

    font=(
        "Segoe UI",
        10
    )
)


path_entry.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(0, 10)
)


# --------------------------------------------------
# Browse button
# --------------------------------------------------

browse_button = tk.Button(
    path_frame,

    text="Browse...",

    command=browse_folder,

    width=12
)


browse_button.pack(
    side="right"
)


# --------------------------------------------------
# Scan and Clean button
# --------------------------------------------------

cleanup_button = tk.Button(
    root,

    text="Scan and Clean",

    command=start_cleanup,

    width=22,
    height=2
)


cleanup_button.pack(
    pady=(18, 10)
)


# --------------------------------------------------
# Progress bar
# --------------------------------------------------

progress_bar = ttk.Progressbar(
    root,

    orient="horizontal",

    mode="determinate",

    length=600,

    style=(
        "Orange.Horizontal.TProgressbar"
    )
)


# IMPORTANT:
#
# We intentionally do NOT call:
#
# progress_bar.pack(...)
#
# here.
#
# Therefore the progress bar is hidden when the
# application first starts.
#
# It will only be shown after the user presses
# "Scan and Clean".


# --------------------------------------------------
# Status label
# --------------------------------------------------

status_label = tk.Label(
    root,

    textvariable=status_var,

    font=(
        "Segoe UI",
        9
    )
)


status_label.pack(
    pady=(0, 5)
)


# --------------------------------------------------
# Start Tkinter
# --------------------------------------------------

root.mainloop()