#!/usr/bin/env python3
"""Verify actual GZoltar 1.7.3 matrices, preserving commas in JVM method signatures.

GZoltar's spectra.csv stores exactly one *unquoted* spectrum name on each
physical line, even when Java parameter lists contain commas.  It must NOT be
parsed as an ordinary multi-column CSV.  Raw source evidence is never modified.
"""
import argparse
import csv
import json
import re
from pathlib import Path


def normalize_test(name):
    return name.strip().replace('::', '#')


def read_spectra(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if lines and lines[0].strip() == 'name':
        lines = lines[1:]
    result = [line.strip() for line in lines]
    if not result or any(not name for name in result):
        raise ValueError('Empty spectrum position')
    return result


def spectrum_class(name):
    if '#' not in name:
        return None
    klass = name.split('#', 1)[0]
    if '$' in klass:
        pkg, rest = klass.split('$', 1)
        klass = pkg + '.' + rest
    return klass


def validate(directory, candidate_file, listed_tests=None, trigger_tests=None, execution_log=None):
    directory, candidate_file = Path(directory), Path(candidate_file)
    with (directory/'tests.csv').open(encoding='utf-8-sig',newline='') as f:
        rt=list(csv.reader(f))
    if not rt: raise ValueError('Empty tests CSV')
    if rt[0] and rt[0][0].strip().lower()=='name':rt=rt[1:]
    if any(not r for r in rt):raise ValueError('Blank test row')
    names=[r[0].strip() for r in rt]
    if len(names)!=len(set(names)):raise ValueError('Duplicate test IDs')
    spectra=read_spectra(directory/'spectra.csv')
    if len(set(spectra))!=len(spectra):raise ValueError('Duplicate full spectrum names')
    candidates={s.strip() for s in candidate_file.read_text(encoding='utf8').splitlines() if s.strip()}
    if not candidates:raise ValueError('Empty candidate production class universe')
    # Do not infer a ground-truth label from the candidate class list.
    unresolved=[]
    mapped_classes=set()
    for name in spectra:
        if '#' not in name or ':' not in name:
            unresolved.append(name)
            continue
        loc=name.rsplit(':',1)[-1]
        if not loc.isdigit(): unresolved.append(name)
        cls=spectrum_class(name)
        if cls is None:unresolved.append(name)
        elif cls not in candidates:unresolved.append(name)
        else:mapped_classes.add(cls)
    matrix=[]; statuses=[]; nonzero=0
    with (directory/'matrix.txt').open(encoding='utf-8') as f:
        for idx,line in enumerate(f):
            tok=line.strip().split()
            trailer=None
            if len(tok)==len(spectra)+1 and tok[-1] in ('+','-'):
                trailer='PASS' if tok.pop()=='+' else 'FAIL'
            if len(tok)!=len(spectra) or any(c not in ('0','1') for c in tok):
                raise ValueError(f'Malformed matrix row {idx+1}: {len(tok)} columns; expected {len(spectra)}')
            if idx>=len(rt):raise ValueError('More matrix rows than tests')
            raw_status=rt[idx][1].strip().upper() if len(rt[idx])>=2 else ''
            status={'PASS':'PASS','PASSED':'PASS','+':'PASS','FAIL':'FAIL','FAILED':'FAIL','ERROR':'FAIL','-':'FAIL'}.get(raw_status)
            if status and trailer and status!=trailer:raise ValueError(f'Test status mismatch at row {idx+1}')
            if not (status or trailer): raise ValueError(f'Missing test status at row {idx+1}')
            statuses.append(status or trailer)
            nonzero+=tok.count('1')
            matrix.append(tok)
    if len(matrix)!=len(names):raise ValueError('Test count mismatch')
    if not ('FAIL' in statuses and 'PASS' in statuses):raise ValueError('Both PASS and FAIL required')
    if not nonzero:raise ValueError('All-zero coverage')
    listed,missing,extra=[],[],[]
    if listed_tests:
        for line in Path(listed_tests).read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line:
                listed.append(normalize_test(line.split(',',1)[-1]))
        missing=sorted(set(listed)-set(names))
        extra=sorted(set(names)-set(listed))
    # Executed tests and report-exported tests are distinct. GZoltar can log a
    # completed test while omitting its row from the exported spectrum matrix.
    logged_execution={}
    if execution_log:
        for test,flag in re.findall(r'^([^\n]+?) has finished! Has it failed\? (true|false)$',
                                    Path(execution_log).read_text(encoding='utf-8',errors='replace'),re.M):
            logged_execution[test] = 'FAIL' if flag=='true' else 'PASS'
    logged_but_not_exported=sorted(set(logged_execution)-set(names)) if execution_log else None
    exported_but_not_logged=sorted(set(names)-set(logged_execution)) if execution_log else None
    conflicting_execution={test: {'log':logged_execution[test], 'export':status}
                           for test,status in zip(names,statuses)
                           if test in logged_execution and logged_execution[test]!=status}
    observed_fail=sorted(x for x,v in zip(names,statuses) if v=='FAIL')
    expected_fail=[]; missing_fail=[]; unexpected_fail=[]
    if trigger_tests:
        expected_fail=sorted(normalize_test(x) for x in Path(trigger_tests).read_text(encoding='utf-8').splitlines() if x.strip())
        missing_fail=sorted(set(expected_fail)-set(observed_fail))
        unexpected_fail=sorted(set(observed_fail)-set(expected_fail))
    result={
       'artifact_type':'REAL_JVM_GZOLTAR_COVERAGE_AUDIT',
       'test_count':len(names),'pass':statuses.count('PASS'),'fail':statuses.count('FAIL'),
       'spectra_positions':len(spectra),'unique_full_spectra_positions':len(set(spectra)),
       'spectrum_names_containing_commas':sum(',' in x for x in spectra),
       'one_cells':nonzero,'zero_coverage_rows':sum(not any(x=='1' for x in row) for row in matrix),
       'candidate_buggy_production_classes':len(candidates),
       'observed_spectrum_classes':len(mapped_classes),
       'unobserved_candidate_classes':sorted(candidates-mapped_classes),
       'unresolved_spectrum_positions':len(set(unresolved)),
       'discovered_test_count':len(listed) if listed_tests else None,
       'discovered_test_missing_from_exported_coverage':missing if listed_tests else None,
       'exported_test_missing_from_discovery':extra if listed_tests else None,
       'completed_tests_in_execution_log':len(logged_execution) if execution_log else None,
       'logged_tests_without_exported_coverage':logged_but_not_exported,
       'exported_tests_without_execution_log':exported_but_not_logged,
       'execution_log_export_status_conflicts':conflicting_execution,
       'independent_trigger_count':len(expected_fail) if trigger_tests else None,
       'trigger_tests_missing_from_gzoltar':missing_fail if trigger_tests else None,
       'unexpected_failing_tests':unexpected_fail if trigger_tests else None,
       'status':'INPUT_STRUCTURE_VALID_WITH_COVERAGE_EXPORT_GAPS' if missing or extra or logged_but_not_exported or exported_but_not_logged else 'INPUT_STRUCTURE_VALID',
       'formal_E01_status':'BLOCKED_UNTIL_COMPLETE_TEST_AND_INDEPENDENT_LABEL_AUDIT',
       'not_checked':['Completeness of coverage export for all executed tests',
                      'Independent fault-method ground-truth labels',
                      'Correct source method signature mapping for formal evaluation',
                      'Published baseline fidelity and fairness',
                      'Complete published E01 protocol'],
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--candidate-file',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--listed-tests',type=Path)
    p.add_argument('--trigger-tests',type=Path)
    p.add_argument('--execution-log',type=Path)
    args=p.parse_args()
    r=validate(args.directory,args.candidate_file,args.listed_tests,args.trigger_tests,args.execution_log)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
