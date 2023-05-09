# PyPCR1000
Port of James Ahlstrom's PCR1000 controller to Python 3 on Raspberry Pi (4b)

This will finally build and control an Icom PCR1000.  

There is a wierd bug where in Windows 10, the radio will 'timeout' and shut down;
no messages are passed on serial when this happens, and the radio can be started right
back up with the power button (button does not change state).  When run from a Raspberry Pi, 
this issue does not happen.

There are still problems with Class DialogSerial() - next on my list to fix.
