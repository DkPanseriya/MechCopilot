@echo off
echo Creating Conda Environment 'mech_copilot_v2'...
call conda env create -f backend/environment.yml
echo Environment created.
echo To activate manually: conda activate mech_copilot_v2
