#!/home/jacob/.python-venvs/automation/bin/python3
# @job test job
# @schedule cron: * * * * *
# @notify.channel general

for i in range(10):
    print("this is job output")
