Vision: pipe in a file, identify the filetype, display an animation of the file sections and data.

Current Framework: pygame-ce

Tools:
    - uv
    - linux `file` at /usr/bin/file

Proof of concept:

    accept a file as an argument
    run file on it; if the filetype is ASCII text, continue. otherwise exit
    using pygame, display the content in hex, in rows of 64 bytes on the left hand of the screen
    after a second, animate these byte encodings moving to the open space on the right of the hex encodings, then turn into their ascii character representations
