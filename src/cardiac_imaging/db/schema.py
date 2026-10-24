"""Data model: every table in cms.duckdb, what each column means, and which columns the analysis uses (standard library only)."""

# Each column: (name, DuckDB type, meaning, used_by_analysis)
CLAIMS_COLUMNS = [
    ('year', 'INTEGER', 'Calendar year of service; taken from the YYYY__ prefix of the Parquet file name.', True),
    ('Rndrng_NPI', 'VARCHAR', 'National Provider Identifier of the rendering (billing) clinician. Unique NPIs = physicians.', True),
    ('Rndrng_Prvdr_Last_Org_Name', 'VARCHAR', 'Provider last name or organization name.', False),
    ('Rndrng_Prvdr_First_Name', 'VARCHAR', 'Provider first name.', False),
    ('Rndrng_Prvdr_MI', 'VARCHAR', 'Provider middle initial.', False),
    ('Rndrng_Prvdr_Crdntls', 'VARCHAR', 'Credentials as reported (e.g. M.D.).', False),
    ('Rndrng_Prvdr_Ent_Cd', 'VARCHAR', 'Entity type: I = individual, O = organization.', False),
    ('Rndrng_Prvdr_St1', 'VARCHAR', 'Practice street address, line 1.', False),
    ('Rndrng_Prvdr_St2', 'VARCHAR', 'Practice street address, line 2.', False),
    ('Rndrng_Prvdr_City', 'VARCHAR', 'Practice city.', False),
    ('Rndrng_Prvdr_State_Abrvtn', 'VARCHAR', 'Practice state postal code; defines the state of each service. '
                                            'Territories and invalid codes are excluded (config.EXCLUDED_AREAS).', True),
    ('Rndrng_Prvdr_State_FIPS', 'VARCHAR', 'State FIPS code (text, keeps leading zeros).', False),
    ('Rndrng_Prvdr_Zip5', 'VARCHAR', 'Practice 5-digit ZIP (text, keeps leading zeros).', False),
    ('Rndrng_Prvdr_RUCA', 'VARCHAR', 'Rural-Urban Commuting Area code of the practice ZIP, stored as text. '
                                    'Cast to a number: ≤ 3.0 = Urban, > 3.0 = Rural, missing = Unknown.', True),
    ('Rndrng_Prvdr_RUCA_Desc', 'VARCHAR', 'Text description of the RUCA code.', False),
    ('Rndrng_Prvdr_Cntry', 'VARCHAR', "Practice country; provider-density analyses keep 'US' only.", True),
    ('Rndrng_Prvdr_Type', 'VARCHAR', 'Provider specialty as derived by CMS. Grouped into radiology (config.RAD_TYPES) '
                                    'and cardiology (config.CARD_TYPES).', True),
    ('Rndrng_Prvdr_Mdcr_Prtcptg_Ind', 'VARCHAR', 'Medicare participating provider (Y/N).', False),
    ('HCPCS_Cd', 'VARCHAR', 'Procedure code. Defines the five modalities (config.MODALITY_CASE): Echo, SPECT, '
                            'Cardiac CTA (75574), Cardiac MRI, Cardiac PET.', True),
    ('HCPCS_Desc', 'VARCHAR', 'Procedure description.', False),
    ('HCPCS_Drug_Ind', 'VARCHAR', 'Whether the code is a drug (Y/N).', False),
    ('Place_Of_Srvc', 'VARCHAR', 'F = facility, O = office (non-facility). Used for the setting segments in Figure 2.', True),
    ('Tot_Benes', 'BIGINT', 'Distinct beneficiaries who received the service from this provider.', False),
    ('Tot_Srvcs', 'DOUBLE', 'Number of services billed — the volume measure behind every rate and count model.', True),
    ('Tot_Bene_Day_Srvcs', 'BIGINT', 'Distinct beneficiary-days of service (carried in the detail extract, not modeled).', True),
    ('Avg_Sbmtd_Chrg', 'DOUBLE', 'Average submitted charge per service.', False),
    ('Avg_Mdcr_Alowd_Amt', 'DOUBLE', 'Average Medicare allowed amount per service.', False),
    ('Avg_Mdcr_Pymt_Amt', 'DOUBLE', 'Average Medicare payment per service.', False),
    ('Avg_Mdcr_Stdzd_Amt', 'DOUBLE', 'Average standardized Medicare payment per service.', False),
]

ENROLLMENT_COLUMNS = [
    ('year', 'BIGINT', 'Enrollment year (2018 or 2023).', True),
    ('state', 'VARCHAR', 'State postal code (50 states + DC; territories removed when the workbook is parsed).', True),
    ('ffs', 'BIGINT', 'Original Medicare (fee-for-service) enrollees — the denominator of every state rate.', True),
]

GV_COLUMNS = [   # only the columns the analysis reads; the table keeps all ~246 raw columns as VARCHAR
    ('YEAR', 'VARCHAR', 'Data year; the models use config.GV_YEAR (2023).', True),
    ('BENE_GEO_LVL', 'VARCHAR', "Geography level (National / State / County); the analysis keeps 'State'.", True),
    ('BENE_GEO_DESC', 'VARCHAR', 'Geography name or postal code; resolved to a state code.', True),
    ('BENE_GEO_CD', 'VARCHAR', 'Geography FIPS code; fallback for resolving the state.', True),
    ('BENE_AGE_LVL', 'VARCHAR', "Age group; the analysis keeps 'All'.", True),
    ('BENE_AVG_AGE', 'VARCHAR', 'Mean beneficiary age — model covariate (z-scored).', True),
    ('BENE_FEML_PCT', 'VARCHAR', '% female beneficiaries — model covariate (z-scored; fractions rescaled to %).', True),
]

TABLES = [
    dict(name='partb_provider_service', kind='VIEW', columns=CLAIMS_COLUMNS, all_columns_listed=True,
         grain='One row per provider (NPI) × HCPCS code × place of service × year.',
         source='CMS Medicare Physician & Other Practitioners — by Provider and Service, 2018–2023 (public use file).',
         built_by='scripts/build_database.py → db.build.build_claims_table (view over ~/Downloads/cms_parquet/YYYY__*.parquet, '
                  'written by scripts/convert_cms_to_parquet.py).',
         size='58,853,705 rows (9.4–10.1 M per year).'),
    dict(name='state_ffs_enrollment', kind='TABLE', columns=ENROLLMENT_COLUMNS, all_columns_listed=True,
         grain='One row per state × year.',
         source="CMS Original Medicare enrollment workbooks ('original medicare enrollment 2018.xlsx' / '… 2023.xlsx').",
         built_by='scripts/build_database.py → db.build.load_state_enrollment (parsed by loaders.enrollment).',
         size='102 rows (51 per year).'),
    dict(name='gv_puf', kind='TABLE', columns=GV_COLUMNS, all_columns_listed=False,
         grain='One row per geography × age group × year (raw file, every value VARCHAR).',
         source='CMS Medicare Geographic Variation public use file (National, State & County).',
         built_by='scripts/build_database.py → db.build.load_gv_puf; cleaned by loaders.demographics.',
         size='~37,000 rows, 246 columns.'),
]

RELATIONSHIPS = [  # (from table, to table, join keys, meaning)
    ('partb_provider_service', 'state_ffs_enrollment', 'Rndrng_Prvdr_State_Abrvtn = state, year',
     'Services per state divided by FFS enrollees → rate per 1,000 beneficiaries (Figures 1, 3–8).'),
    ('partb_provider_service', 'gv_puf', 'Rndrng_Prvdr_State_Abrvtn = resolved state, year = 2023',
     'State mean age and % female join the CTA density models as covariates (Figures 8, 9, S1, S2).'),
]


def validate(con):
    """Compare the live database with this data model; returns a list of problems (empty = matches)."""
    problems = []
    present = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    for t in TABLES:
        if t['name'] not in present:
            problems.append(f"missing table {t['name']}")
            continue
        live = {r[0]: r[1] for r in con.execute(f"DESCRIBE {t['name']}").fetchall()}
        for col, typ, _, _ in t['columns']:
            if col not in live:
                problems.append(f"{t['name']}.{col} missing")
            elif live[col] != typ:
                problems.append(f"{t['name']}.{col} is {live[col]}, expected {typ}")
        if t['all_columns_listed']:
            extra = sorted(set(live) - {c[0] for c in t['columns']})
            if extra:
                problems.append(f"{t['name']} has undocumented columns {extra}")
    return problems
