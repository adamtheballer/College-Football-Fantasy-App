"""Prepare a disposable XCTest host; never change the production Xcode targets.
Requires an isolated localhost API at port 18437 and CFF_NAME_CHANGE_E2E_DATABASE_URL.
Use the printed NativeChecks project with xcodebuild test on an isolated simulator.
"""
from pathlib import Path
import plistlib, json, urllib.request, urllib.error, subprocess, os, sys, tempfile, uuid
from xml.sax.saxutils import escape
root=Path(__file__).resolve().parents[3]
harness=Path(tempfile.mkdtemp(prefix='cff-native-settings-'))/'web/ios/App'
harness.mkdir(parents=True,exist_ok=True)
(harness.parent/'debug.xcconfig').symlink_to(root/'web/ios/debug.xcconfig')
if not os.environ.get('CFF_NAME_CHANGE_E2E_DATABASE_URL'): raise SystemExit('Supply the guarded isolated test database URL.')
for name,source in [('App',root/'web/ios/App/App'),('CapApp-SPM',root/'web/ios/App/CapApp-SPM')]:
 target=harness/name
 if not target.exists(): target.symlink_to(source,target_is_directory=True)
modules=harness.parents[1]/'node_modules'
if not modules.exists():modules.symlink_to(root/'web/node_modules',target_is_directory=True)
project=harness/'App.xcodeproj';(project/'xcshareddata/xcschemes').mkdir(parents=True,exist_ok=True)
s=(root/'web/ios/App/App.xcodeproj/project.pbxproj').read_text()
source=str(root/'web/ios/tests/AccountSettingsNativeTests.swift')
entries={
'PBXBuildFile': 'A11000000000000000000001 = {isa = PBXBuildFile; fileRef = A11000000000000000000002; };',
'PBXFileReference': f'A11000000000000000000002 = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "{source}"; sourceTree = "<absolute>"; }};\n A11000000000000000000003 = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; path = NativeChecks.xctest; sourceTree = BUILT_PRODUCTS_DIR; }};',
'PBXNativeTarget': 'A11000000000000000000004 = {isa = PBXNativeTarget; buildConfigurationList = A11000000000000000000005; buildPhases = (A11000000000000000000006,); buildRules = (); dependencies = (A11000000000000000000007,); name = NativeChecks; productName = NativeChecks; productReference = A11000000000000000000003; productType = "com.apple.product-type.bundle.unit-test"; };',
'PBXSourcesBuildPhase': 'A11000000000000000000006 = {isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (A11000000000000000000001,); runOnlyForDeploymentPostprocessing = 0; };',
'XCConfigurationList': 'A11000000000000000000005 = {isa = XCConfigurationList; buildConfigurations = (A11000000000000000000008,); defaultConfigurationIsVisible = 0; defaultConfigurationName = Debug; };',
'XCBuildConfiguration': 'A11000000000000000000008 = {isa = XCBuildConfiguration; buildSettings = { BUNDLE_LOADER = "$(TEST_HOST)"; TEST_HOST = "$(BUILT_PRODUCTS_DIR)/App.app/App"; GENERATE_INFOPLIST_FILE = YES; IPHONEOS_DEPLOYMENT_TARGET = 15.0; SDKROOT = iphoneos; PRODUCT_BUNDLE_IDENTIFIER = org.collegefantasyfootball.app.localChecks; PRODUCT_NAME = "$(TARGET_NAME)"; SWIFT_VERSION = 5.0; TARGETED_DEVICE_FAMILY = "1,2"; CODE_SIGNING_ALLOWED = NO; }; name = Debug; };'
}
for section,entry in entries.items(): s=s.replace(f'/* Begin {section} section */',f'/* Begin {section} section */\n{entry}\n')
s=s.replace('/* End PBXBuildFile section */','/* End PBXBuildFile section */\n A11000000000000000000007 = {isa = PBXTargetDependency; target = 504EC3031FED79650016851F; };')
s=s.replace('targets = (','targets = (\nA11000000000000000000004,')
s=s.replace('504EC3051FED79650016851F /* Products */,','504EC3051FED79650016851F /* Products */,\n A11000000000000000000002,')
s=s.replace('504EC3041FED79650016851F /* App.app */,','504EC3041FED79650016851F /* App.app */,\n A11000000000000000000003,')
info=plistlib.loads((root/'web/ios/App/App/Info.plist').read_bytes());info['NSAppTransportSecurity']={'NSAllowsArbitraryLoads':True}
localinfo=harness/'LocalAppInfo.plist';localinfo.write_bytes(plistlib.dumps(info));s=s.replace('INFOPLIST_FILE = App/Info.plist;',f'INFOPLIST_FILE = "{localinfo}";')
(project/'project.pbxproj').write_text(s)
email=f'name-e2e-native-{uuid.uuid4().hex}@example.com'
req=urllib.request.Request('http://127.0.0.1:18437/auth/signup', data=json.dumps({'first_name':'Old Native Manager','email':email,'password':'StrongPass123!'}).encode(),headers={'Content-Type':'application/json'})
try: auth=json.load(urllib.request.urlopen(req))
except urllib.error.HTTPError as e:
 if e.code!=409:raise
 req=urllib.request.Request('http://127.0.0.1:18437/auth/login', data=json.dumps({'email':email,'password':'StrongPass123!'}).encode(),headers={'Content-Type':'application/json'})
 auth=json.load(urllib.request.urlopen(req))
subprocess.run([sys.executable,str(root/'scripts/seed_name_change_e2e.py'),str(auth['user']['id']),'--legacy-avatar'],check=True,env=os.environ.copy())
variables={'CFF_NATIVE_TEST_ACCOUNT_ID':str(auth['user']['id']),'CFF_NATIVE_TEST_TOKEN':auth['access_token'],'CFF_NATIVE_TEST_EXPIRES_AT':auth['access_token_expires_at']}
env=''.join(f'<EnvironmentVariable key="{k}" value="{escape(v,{chr(34):"&quot;"})}" isEnabled="YES"/>' for k,v in variables.items())
ref=lambda uid,name:f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid}" BuildableName="{name}" BlueprintName="{name.split(".")[0]}" ReferencedContainer="container:App.xcodeproj"/>'
scheme=f'''<?xml version="1.0" encoding="UTF-8"?><Scheme LastUpgradeVersion="2600" version="1.3"><BuildAction parallelizeBuildables="NO" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="NO" buildForProfiling="NO" buildForArchiving="NO" buildForAnalyzing="NO">{ref('A11000000000000000000004','NativeChecks.xctest')}</BuildActionEntry></BuildActionEntries></BuildAction><TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="NO"><Testables><TestableReference skipped="NO">{ref('A11000000000000000000004','NativeChecks.xctest')}</TestableReference></Testables><EnvironmentVariables>{env}</EnvironmentVariables></TestAction></Scheme>'''
(project/'xcshareddata/xcschemes/NativeChecks.xcscheme').write_text(scheme)
print('Disposable NativeChecks project:',project)
print('Isolated test account ID:',auth['user']['id'])
