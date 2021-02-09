import subprocess
import sys

def runCmd(cmd):
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    return output

pref = ""
for line in runCmd("kubectl get pod").split():
    if line[:4] == "ssc-":
        pref = line[4:16]

myTemplate = "kubectl get configmap ssc-{}-sts-{}-cfg-map -o yaml"
name = sys.argv[1]
cmd = myTemplate.format(pref, name)
print runCmd(cmd)
