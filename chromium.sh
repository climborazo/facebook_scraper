
#!/bin/bash

if lsof -Pi :9222 -sTCP:LISTEN -t >/dev/null ; then
    echo "Chromium Is Running On Port 9222..."
    exit 0
fi

nohup chromium --remote-debugging-port=9222 >/dev/null 2>&1 &

disown

echo "Chromium Is Running In Background - Port 9222..."
