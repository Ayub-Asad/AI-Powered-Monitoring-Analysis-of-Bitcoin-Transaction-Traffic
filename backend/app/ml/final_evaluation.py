"""Additive seed-405 amendment: identity inventory, reservation, one-shot evaluation.

The original tuning code and freeze remain byte-for-byte unchanged. No fitting or
calibration occurs here. Regression tests must never generate reserved seed 405.
"""
import argparse
import ast
import copy
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import numpy as np
import pandas as pd
from .schema import ROOT, digest, from_transactions
from .tuning import read_json, exclusive_json, verify_tuning
from .workflow import read_verified
from .artifacts import load_artifact
from .scoring import risk_scores
from .evaluation import align_truth, seed_summary
from .tuning_analysis import operating_metrics, operating_seed_summary

FINAL_SPEC = {'seed': 405, 'start_time': '2025-04-01T00:00:00+00:00', 'normal': 15300, 'anomalous': 2700}


def validate_amendment(config, frozen, root):
    if set(config) != {'version','run_dir','report_dir','final_data_dir','fixture_inventory','final_test','supersedes_seed','reason','approval_date'}:
        raise ValueError('unexpected amendment fields; model policies cannot be overridden')
    if config['version'] != 'transaction-iforest-final405-v1' or config['final_test'] != FINAL_SPEC or config['supersedes_seed'] != 404:
        raise ValueError('only the approved 404-to-405 reservation is accepted')
    if not config['reason'] or not config['approval_date']:
        raise ValueError('seed-change reason and approval date required')
    if frozen['config']['final_test'] != {**FINAL_SPEC, 'seed': 404}:
        raise ValueError('unexpected original reservation')
    for key in ('run_dir', 'report_dir'):
        if config[key] != frozen['config'][key]:
            raise ValueError('amendment cannot redirect frozen run or reports')
    root = Path(root).resolve()
    for key in ('run_dir', 'report_dir', 'final_data_dir', 'fixture_inventory'):
        path = (root/config[key]).resolve()
        if path == root or not path.is_relative_to(root):
            raise ValueError('amendment path escapes workspace')
    if not (root/config['final_data_dir']).resolve().is_relative_to(root/'data/ml/tuning'):
        raise ValueError('final corpus must use separate ignored tuning directory')
    if (root/config['final_data_dir']).resolve() == (root/frozen['config']['final_data_dir']).resolve():
        raise ValueError('new seed must have a new corpus directory')
    inventory = (root/config['fixture_inventory']).resolve()
    if inventory.parent != (root/config['run_dir']).resolve() or inventory.name != 'fixture_inventory.json':
        raise ValueError('unexpected fixture inventory location')


def addresses(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value) if value.startswith('[') else value.split('|')
    raise ValueError('invalid identity address list')


def identity_bundle(frame, groups=None, scope=None):
    required = {'txid', 'timestamp', 'input_addresses', 'output_addresses'}
    if not required <= set(frame):
        raise ValueError('fixture is missing transaction identities')
    if frame.txid.duplicated().any():
        raise ValueError('duplicate fixture TXIDs')
    times = pd.to_datetime(frame.timestamp, utc=True)
    ids = {'txid': set(frame.txid), 'wallet': {a for col in ('input_addresses','output_addresses') for v in frame[col] for a in addresses(v)},
           'scoped_actor': set(), 'scoped_scenario': set(), 'raw_scenario': set()}
    if groups is not None:
        if groups.txid.duplicated().any() or set(groups.txid) != ids['txid'] or groups[['actor_id','scenario_id']].isna().any().any():
            raise ValueError('fixture grouping coverage mismatch')
        if not scope:
            raise ValueError('corpus scope required for local actor names')
        ids['scoped_actor'] = {scope+':'+a.split(':',1)[-1] for a in groups.actor_id}
        ids['raw_scenario'] = {s.split(':',1)[-1] for s in groups.scenario_id}
        ids['scoped_scenario'] = {scope+':'+s for s in ids['raw_scenario']}
    return {'records': len(frame), 'start': times.min().isoformat() if len(frame) else None,
            'end': times.max().isoformat() if len(frame) else None,
            'grouping_available': groups is not None, 'scope': scope,
            'identities': {k: sorted(v) for k,v in ids.items()}}


def collect_inventory(config, root=ROOT, temp_root=None):
    """Collect/reconstruct known fixtures without producing or inspecting seed 405."""
    root = Path(root)
    frozen = verify_tuning(root/config['run_dir'], root)
    validate_amendment(config, frozen, root)
    destination = root/config['fixture_inventory']; report = root/config['report_dir']/'fixture_manifest.json'
    if destination.exists() or report.exists():
        raise FileExistsError('fixture inventory already exists')
    entries = []; sources = {}; seen = set()
    def add(name, frame, groups=None, scope=None, chronological=False, evidence=None):
        entries.append({'name': name, 'must_precede_final': chronological, 'evidence': evidence,
                        **identity_bundle(frame, groups, scope)})
    base_data = root/frozen['baseline_config']['data_dir']
    for name in ('train','validation','test'):
        manifest = frozen['corpus_manifest']
        tx = read_verified(base_data, name, 'transactions', manifest)
        groups = read_verified(base_data, name, 'groups', manifest)
        add(name, tx, groups, name, True, {'manifest_sha256': digest(base_data/'manifest.json')})
    for name in ('development','regression'):
        tx_path = root/f'data/v2/{name}.jsonl'; groups_path = root/f'data/v2/{name}.ground_truth.jsonl'
        # Ground-truth files are read for identities only; no labels are retained.
        tx = pd.read_json(tx_path, lines=True)[['txid','timestamp','input_addresses','output_addresses']]
        groups = pd.read_json(groups_path, lines=True)[['txid','actor_id','scenario_id']]
        add('tracked-v2-'+name, tx, groups, 'v2-'+name, True,
            {'transactions_sha256': digest(tx_path), 'groups_sha256': digest(groups_path)})
    legacy = root/'data/btc_synthetic_dataset.csv'
    add('tracked-v1', pd.read_csv(legacy, usecols=['txid','timestamp','input_addresses','output_addresses']), chronological=True,
        evidence={'transactions_sha256': digest(legacy)})
    temp_root = Path(temp_root) if temp_root else Path(os.environ.get('TEMP','/tmp'))/'pytest-of-Ayub Asad'
    retained = sorted(temp_root.rglob('*.transactions.jsonl')) if temp_root.exists() else []
    for path in retained:
        groups_path = path.with_name(path.name.replace('.transactions.', '.groups.'))
        key = (digest(path), digest(groups_path) if groups_path.exists() else None)
        sources[str(path.relative_to(temp_root)).replace('\\','/')] = {'transactions_sha256': key[0], 'groups_sha256': key[1]}
        if key in seen:
            continue
        seen.add(key)
        name = path.name.split('.')[0]; mpath = path.parent/'manifest.json'; spec = None
        if mpath.exists():
            spec = read_json(mpath).get('corpora',{}).get(name,{}).get('generation')
        if spec and spec['seed'] == 405:
            raise ValueError('reserved seed 405 already appears in a regression fixture; stop')
        tx = pd.read_json(path,lines=True)
        groups = pd.read_json(groups_path,lines=True) if groups_path.exists() else None
        add(f'retained-fixture-{len(seen):02d}',tx,groups, 'fixture-'+key[0][:16], False,
            {'transactions_sha256': key[0], 'groups_sha256': key[1], 'generation': spec})
    sys.path.insert(0, str(ROOT))
    from scripts.dataset_v2 import BitcoinDatasetV2Generator
    from scripts.btc_synthetic_dataset_generator import BitcoinDatasetGenerator
    # Includes earlier deleted 404 fixtures and all source-defined generated recipes.
    recipes = [(101,60,0,'2025-01-01'),(202,60,20,'2025-02-01'),(303,60,20,'2025-03-01'),
               (404,60,20,'2025-04-01'),(9404,60,20,'2025-04-01')]
    recipes += [(42,0,n,'2025-01-01') for n in (0,1,2,7,150)]
    for seed, normal, anomalous, date in recipes:
        generator = BitcoinDatasetV2Generator(seed, datetime.fromisoformat(date+'T00:00:00+00:00'))
        rows = generator.generate(normal,anomalous)
        if not rows:
            continue
        tx = pd.DataFrame([{k: asdict(row)[k] for k in ('txid','timestamp','input_addresses','output_addresses')} for row in rows])
        groups = pd.DataFrame(generator.ground_truth)[['txid','actor_id','scenario_id']]
        add(f'reconstructed-v2-{seed}-{normal}-{anomalous}',tx,groups,f'fixture-v2-{seed}-{normal}-{anomalous}',False,
            {'recipe': {'seed':seed,'normal':normal,'anomalous':anomalous,'start_time':date}, 'reason':'source-defined or known earlier fixture, including deleted temporary files'})
    rows = BitcoinDatasetGenerator(7).generate(600,120)
    add('reconstructed-v1-7',pd.DataFrame([asdict(row) for row in rows]),chronological=False,
        evidence={'recipe':{'seed':7,'normal':600,'anomalous':120,'start_time':'2025-01-01'}})
    # Conservative union of source literals and helper-generated integer TXIDs.
    # This also covers handwritten split/ranking fixtures without real wallets.
    literals = set(); test_sources = {}
    for path in sorted((root/'backend/tests').glob('*.py')):
        test_sources[str(path.relative_to(root)).replace('\\','/')] = digest(path)
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        literals.update(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str))
    manual_ids = {f'{i:064x}' for i in range(4096)} | {c*64 for c in '0123456789abcdef'} | {s.lower() for s in literals if re.fullmatch('[0-9a-fA-F]{64}',s)}
    manual_wallets = {s for s in literals if re.fullmatch(r'(?:bc1|[13])[A-Za-z0-9]{20,90}',s)}
    manual_wallets |= {part for text in literals for part in text.split('|') if 0 < len(part) <= 100 and not any(c.isspace() for c in part)}
    manual_wallets |= {name+suffix for name in ('train','validation','test') for suffix in ('a','b')}
    entries.append({'name':'handwritten-fixture-identity-superset','must_precede_final':False,
        'records':None,'start':None,'end':None,'grouping_available':True,'scope':'manual',
        'evidence':{'integer_txid_range':'0..4095 (conservative superset of helper calls)','source_files':test_sources},
        'identities':{'txid':sorted(manual_ids|{'a','b','c','d','e','train','validation','test','other'}),
        'wallet':sorted(manual_wallets),'scoped_actor':['train:actor','validation:actor','test:actor'],
        'scoped_scenario':['train:train','validation:validation','test:test'],'raw_scenario':['train','validation','test']}})
    inventory = {'entries':entries,'retained_sources':sources,'test_source_hashes':test_sources,
                 'known_generated_fixture_seeds':[7,42,101,202,303,404,9404],
                 'limits':'Audits known source-defined, retained, and reconstructed fixtures; cannot inventory unknown external/private data. Legacy/manual rows may have no actor/scenario metadata.'}
    exclusive_json(destination,inventory)
    summary = {**{k:v for k,v in inventory.items() if k not in ('entries','retained_sources')},
        'retained_transaction_files':len(retained),'unique_retained_identity_files':len(seen),
        'inventory_sha256':digest(destination),
        'entries':[{**{k:v for k,v in e.items() if k!='identities'},'identity_counts':{k:len(v) for k,v in e['identities'].items()}} for e in entries]}
    exclusive_json(report,summary)
    return {'entries':len(entries),'retained_files':len(retained),'inventory_sha256':digest(destination)}


def audit_identities(final_tx, final_groups, inventory, scope='final-405'):
    if not final_groups.corpus.eq(scope).all() or any(not final_groups[col].str.startswith(scope+':').all() for col in ('actor_id','scenario_id')):
        raise ValueError('incorrect final corpus scope')
    final = identity_bundle(final_tx,final_groups,scope)
    comparisons = []; failed = []
    for entry in inventory['entries']:
        overlaps = {k:len(set(final['identities'][k]) & set(v)) for k,v in entry['identities'].items()}
        comparable = bool(final['start'] and entry['start'])
        time_overlap = bool(comparable and pd.Timestamp(entry['end']) >= pd.Timestamp(final['start']) and pd.Timestamp(final['end']) >= pd.Timestamp(entry['start']))
        chronological = bool(comparable and pd.Timestamp(entry['end']) < pd.Timestamp(final['start']))
        if any(overlaps.values()) or (entry['must_precede_final'] and not chronological):
            failed.append(entry['name'])
        comparisons.append({'reference':entry['name'],'overlaps':overlaps,'time_overlap':time_overlap if comparable else None,
            'must_precede_final':entry['must_precede_final'],'chronologically_before_final':chronological if comparable else None,
            'time_policy':'strict earlier partition' if entry['must_precede_final'] else 'independent regression fixture; shared calendar permitted',
            'grouping_available':entry['grouping_available']})
    if failed:
        raise ValueError('final identity/chronology audit failed: '+', '.join(failed))
    return {'passed':True,'final':{k:v for k,v in final.items() if k!='identities'},
            'final_identity_counts':{k:len(v) for k,v in final['identities'].items()},'comparisons':comparisons,
            'scope_note':'Actors are local generator names scoped by independently generated corpus; raw scenario hashes and actual wallets are also compared. Scope does not establish wallet ownership.'}


def reserve(config, root=ROOT):
    root=Path(root); run=root/config['run_dir']; report=root/config['report_dir']
    frozen=verify_tuning(run,root); validate_amendment(config,frozen,root)
    for path in (root/config['final_data_dir'],run/'final_started.json',run/'final_completed.json',run/'final_405_reservation.json',report/'final_evaluation.json'):
        if path.exists(): raise FileExistsError(f'final output/reservation already exists: {path.name}')
    manifest=read_json(report/'fixture_manifest.json')
    if digest(root/config['fixture_inventory'])!=manifest['inventory_sha256']:
        raise ValueError('fixture inventory changed')
    reservation={'status':'reserved','amendment':config,'original_frozen_sha256':digest(run/'frozen.json'),
                 'models':frozen['models'],'selected_parameters':frozen['selected_parameters'],
                 'ranking_budgets':frozen['config']['alert_budgets'],
                 'fixture_inventory_sha256':manifest['inventory_sha256'],
                 'fixture_manifest_sha256':digest(report/'fixture_manifest.json'),
                 'amendment_source_sha256':digest(Path(__file__)),
                 'unchanged_policy':'All fitting, preprocessing, selected artifacts, thresholds and ranking/selection/comparison policies are inherited verbatim from original freeze.'}
    exclusive_json(run/'final_405_reservation.json',reservation)
    seal={'reservation_sha256':digest(run/'final_405_reservation.json')}
    exclusive_json(run/'final_405_seal.json',seal)
    exclusive_json(report/'seed_change.json',{**reservation,**seal})
    return seal


def verify_reservation(config,root=ROOT):
    root=Path(root);run=root/config['run_dir'];report=root/config['report_dir']
    frozen=verify_tuning(run,root);validate_amendment(config,frozen,root)
    seal=read_json(run/'final_405_seal.json'); reservation=read_json(run/'final_405_reservation.json')
    if digest(run/'final_405_reservation.json')!=seal['reservation_sha256'] or reservation['amendment']!=config:
        raise ValueError('final reservation changed')
    if reservation['original_frozen_sha256']!=digest(run/'frozen.json') or reservation['models']!=frozen['models']:
        raise ValueError('original model decisions changed')
    if reservation['amendment_source_sha256']!=digest(Path(__file__)):
        raise ValueError('final evaluation source changed after reservation')
    if reservation['fixture_inventory_sha256']!=digest(root/config['fixture_inventory']) or reservation['fixture_manifest_sha256']!=digest(report/'fixture_manifest.json'):
        raise ValueError('fixture audit inventory changed')
    return frozen,reservation


def generate_corpus(spec,directory,scope):
    """Production caller verifies reservation; unit fixtures use other seeds."""
    sys.path.insert(0,str(ROOT))
    from scripts.dataset_v2 import BitcoinDatasetV2Generator
    from scripts.prepare_ml_datasets import write_lines
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    g=BitcoinDatasetV2Generator(spec['seed'],datetime.fromisoformat(spec['start_time']))
    rows=g.generate(spec['normal'],spec['anomalous'])
    tx=[{k:v for k,v in asdict(row).items() if k not in {'label','anomaly_type'}} for row in rows]
    groups=[{'txid':r['txid'],'corpus':scope,'actor_id':scope+':'+r['actor_id'],'scenario_id':scope+':'+r['scenario_id']} for r in g.ground_truth]
    labels=[{k:r[k] for k in ('txid','label','anomaly_type')} for r in g.ground_truth]
    for suffix,values in (('transactions',tx),('groups',groups),('labels',labels)):
        write_lines(directory/f'final.{suffix}.jsonl',values)
    manifest={'corpora':{'final':{'generation':spec,'records':len(tx),'complete_scenarios':True,
              'files':{p.name:digest(p) for p in directory.glob('*.jsonl')}}}}
    exclusive_json(directory/'manifest.json',manifest)
    return manifest


def evaluate_final(config,root=ROOT):
    started=time.perf_counter();root=Path(root);run=root/config['run_dir'];report=root/config['report_dir'];directory=root/config['final_data_dir']
    frozen,reservation=verify_reservation(config,root)
    if directory.exists() or (report/'final_evaluation.json').exists():
        raise FileExistsError('final corpus/results already exist; no repeat evaluation')
    exclusive_json(run/'final_started.json',{'seed':config['final_test']['seed'],'reservation_sha256':digest(run/'final_405_reservation.json')})
    try:
        models={name:load_artifact(run/spec['path']) for name,spec in frozen['models'].items()}
        begin=time.perf_counter();manifest=generate_corpus(config['final_test'],directory,'final-405');generation_seconds=time.perf_counter()-begin
        if manifest['corpora']['final']['generation']!=config['final_test'] or manifest['corpora']['final']['records']!=sum(config['final_test'][k] for k in ('normal','anomalous')):
            raise ValueError('generated corpus differs from approved configuration')
        tx=read_verified(directory,'final','transactions',manifest)
        groups=read_verified(directory,'final','groups',manifest)
        audit=audit_identities(tx,groups,read_json(root/config['fixture_inventory']))
        exclusive_json(report/'final_manifest.json',{**manifest,'identity_audit':audit,'generation_seconds':generation_seconds,
                       'seed_change':config,'original_frozen_sha256':reservation['original_frozen_sha256'],
                       'reservation_sha256':digest(run/'final_405_reservation.json')})
        ids,matrix=from_transactions(tx);scenario_ids=groups.set_index('txid').loc[list(ids)].scenario_id.to_numpy()
        scores={};timings={}
        for name,(model,threshold,metadata) in models.items():
            begin=time.perf_counter();scores[name]=risk_scores(model,matrix);timings[name]=time.perf_counter()-begin
        pd.DataFrame({'txid':ids,**scores}).to_csv(run/'final_scores.csv',index=False,mode='x')
        verify_reservation(config,root)
        # All identity/chronology checks and all model scoring precede this read.
        y,categories=align_truth(ids,read_verified(directory,'final','labels',manifest))
        if int(y.sum())!=config['final_test']['anomalous'] or int((~y).sum())!=config['final_test']['normal']:
            raise ValueError('final label counts differ from reservation')
        results={name:operating_metrics(values,y,categories,ids,models[name][1]['threshold'],
                 frozen['models'][name]['budget_cutoffs'],frozen['config']['alert_budgets'],scenario_ids) for name,values in scores.items()}
        result={'population':'fresh final seed 405 April 2025','models':results,'selected_parameters':frozen['selected_parameters'],
                'final_feature_shape':list(matrix.shape),'seed_change':config,
                'seed_summary':{kind:seed_summary([results[f'{kind}{s}'] for s in (42,43,44)]) for kind in ('tuned-','baseline-iforest-')},
                'operating_seed_summary':{kind:operating_seed_summary([results[f'{kind}{s}'] for s in (42,43,44)]) for kind in ('tuned-','baseline-iforest-')},
                'generation_seconds':generation_seconds,'score_seconds':timings,'total_seconds':time.perf_counter()-started,
                'original_frozen_sha256':reservation['original_frozen_sha256'],'reservation_sha256':digest(run/'final_405_reservation.json'),
                'scores_sha256':digest(run/'final_scores.csv'),'interpretation':'One final evaluation, no refitting/calibration/selection. Same synthetic generator; not deployment accuracy or evidence of criminal activity.'}
        exclusive_json(report/'final_evaluation.json',result)
        exclusive_json(run/'final_completed.json',{'seed':405,'report_sha256':digest(report/'final_evaluation.json')})
        return {'population':result['population'],'seed_summary':result['seed_summary'],'seconds':result['total_seconds']}
    except Exception as error:
        exclusive_json(run/'final_failed.json',{'error_type':type(error).__name__,'message':str(error),'policy':'Stop; no automatic retry or alternate seed.'})
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['inventory','reserve','evaluate']);p.add_argument('--config',type=Path,required=True)
    args=p.parse_args();c=read_json(args.config)
    print(json.dumps({'inventory':collect_inventory,'reserve':reserve,'evaluate':evaluate_final}[args.command](c),indent=2))


if __name__=='__main__':
    main()
