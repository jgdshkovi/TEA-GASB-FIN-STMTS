"""
TEA Account Code to GASB Category Mapping Rules
Based on TEA FASRG documentation and GASB standards

This module uses pattern matching for comprehensive account code categorization:
- Object codes (positions 5-8): 1XXX=Assets, 2XXX=Liabilities, 3XXX=Net Position, etc.
- Fund codes (positions 0-2): 1XX=General Fund, 2XX=Special Revenue, etc.
- Function codes (positions 3-4): Used for program expense categorization

Pattern matching ensures all account codes are properly categorized, not just hardcoded ones.
"""

# TEA Object Code Categories (first digit determines major category)
TEA_OBJECT_CATEGORIES = {
    '1': 'Assets',
    '2': 'Liabilities', 
    '3': 'Fund Balances/Net Position',
    '4': 'Clearing Accounts',
    '5': 'Revenues',
    '6': 'Expenditures/Expenses',
    '7': 'Other Resources/Non-operating Revenues',
    '8': 'Other Uses/Non-operating Expenses'
}

# GASB Statement Categories for Government-wide Financial Statements
GASB_CATEGORIES = {
    # Assets
    'current_assets': {
        'description': 'Current Assets',
        'tea_codes': ['1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190',  # Cash and equivalents
                     '1210', '1220', '1225', '1230', '1240', '1250', '1260', '1267', '1270', '1280', '1290',  # Receivables
                     '1300', '1310', '1320', '1330', '1340', '1350', '1360', '1370', '1380', '1390',  # Other current assets
                     '1410', '1420', '1430', '1440', '1450', '1460', '1470', '1480', '1490']  # Prepaid items
    },
    'capital_assets': {
        'description': 'Capital Assets',
        'tea_codes': ['1510', '1520', '1530', '1540', '1550', '1560', '1570', '1580', '1590']  # Land, buildings, equipment
    },
    'deferred_outflows': {
        'description': 'Deferred Outflows of Resources',
        'tea_codes': ['1700', '1701', '1702', '1703', '1704', '1705', '1706', '1707', '1708', '1709']
    },
    
    # Liabilities
    'current_liabilities': {
        'description': 'Current Liabilities',
        'tea_codes': ['2110', '2120', '2130', '2140', '2150', '2160', '2165', '2170', '2180', '2190',  # Payables
                     '2210', '2220', '2230', '2240', '2250', '2260', '2270', '2280', '2290',  # Accrued liabilities
                     '2300', '2310', '2320', '2330', '2340', '2350', '2360', '2370', '2380', '2390']  # Other current liabilities
    },
    'long_term_liabilities': {
        'description': 'Long-term Liabilities',
        'tea_codes': ['2410', '2420', '2430', '2440', '2450', '2460', '2470', '2480', '2490',  # Long-term debt
                     '2501', '2502', '2510', '2520', '2530', '2540', '2545', '2550', '2560', '2570', '2580', '2590']  # Other long-term liabilities
    },
    'deferred_inflows': {
        'description': 'Deferred Inflows of Resources',
        'tea_codes': ['2600', '2601', '2602', '2603', '2604', '2605', '2606', '2607', '2608', '2609']
    },
    
    # Net Position
    'net_investment_capital_assets': {
        'description': 'Net Investment in Capital Assets',
        'tea_codes': ['3200', '3210', '3220', '3230', '3240', '3250', '3260', '3270', '3280', '3290']
    },
    'restricted_net_position': {
        'description': 'Restricted Net Position',
        'tea_codes': ['3300', '3310', '3320', '3330', '3340', '3350', '3360', '3370', '3380', '3390',
                     '3400', '3410', '3420', '3430', '3440', '3450', '3460', '3470', '3480', '3490',
                     '3500', '3510', '3520', '3530', '3540', '3550', '3560', '3570', '3580', '3590',
                     '3600', '3610', '3620', '3630', '3640', '3650', '3660', '3670', '3680', '3690',
                     '3700', '3710', '3720', '3730', '3740', '3750', '3760', '3770', '3780', '3790',
                     '3800', '3810', '3820', '3830', '3840', '3850', '3860', '3870', '3880', '3890']
    },
    'unrestricted_net_position': {
        'description': 'Unrestricted Net Position',
        'tea_codes': ['3900', '3910', '3920', '3930', '3940', '3950', '3960', '3970', '3980', '3990']
    },
    
    # Revenues
    'program_revenues': {
        'description': 'Program Revenues',
        'tea_codes': ['5100', '5110', '5120', '5130', '5140', '5150', '5160', '5170', '5180', '5190',  # Charges for services
                     '5200', '5210', '5220', '5230', '5240', '5250', '5260', '5270', '5280', '5290',  # Operating grants
                     '5300', '5310', '5320', '5330', '5340', '5350', '5360', '5370', '5380', '5390']  # Capital grants
    },
    'general_revenues': {
        'description': 'General Revenues',
        'tea_codes': ['5400', '5410', '5420', '5430', '5440', '5450', '5460', '5470', '5480', '5490',  # Property taxes
                     '5500', '5510', '5520', '5530', '5540', '5550', '5560', '5570', '5580', '5590',  # Other taxes
                     '5600', '5610', '5620', '5630', '5640', '5650', '5660', '5670', '5680', '5690',  # Investment earnings
                     '5700', '5710', '5720', '5730', '5740', '5750', '5760', '5770', '5780', '5790',  # Local and intermediate sources
                     '5800', '5810', '5820', '5830', '5840', '5850', '5860', '5870', '5880', '5890',  # State revenues
                     '5900', '5910', '5920', '5930', '5940', '5950', '5960', '5970', '5980', '5990']  # Federal revenues
    },
    
    # Expenses
    'program_expenses': {
        'description': 'Program Expenses',
        'tea_codes': ['6100', '6110', '6120', '6130', '6140', '6150', '6160', '6170', '6180', '6190',  # Instruction
                     '6200', '6210', '6220', '6230', '6240', '6250', '6260', '6270', '6280', '6290',  # Support services
                     '6300', '6310', '6320', '6330', '6340', '6350', '6360', '6370', '6380', '6390',  # Operation and maintenance
                     '6400', '6410', '6420', '6430', '6440', '6450', '6460', '6470', '6480', '6490',  # Auxiliary enterprises
                     '6500', '6510', '6520', '6530', '6540', '6550', '6560', '6570', '6580', '6590']  # Other programs
    },
    'general_expenses': {
        'description': 'General Expenses',
        'tea_codes': ['6600', '6610', '6620', '6630', '6640', '6650', '6660', '6670', '6680', '6690',  # General administration
                     '6700', '6710', '6720', '6730', '6740', '6750', '6760', '6770', '6780', '6790',  # Interest on debt
                     '6800', '6810', '6820', '6830', '6840', '6850', '6860', '6870', '6880', '6890',  # Capital outlay
                     '6900', '6910', '6920', '6930', '6940', '6950', '6960', '6970', '6980', '6990']  # Other expenses
    },
    
    # Other Resources and Uses
    'other_resources': {
        'description': 'Other Resources & Non-operating Revenues',
        'tea_codes': ['7000', '7010', '7020', '7030', '7040', '7050', '7060', '7070', '7080', '7090',  # Investment earnings
                     '7100', '7110', '7120', '7130', '7140', '7150', '7160', '7170', '7180', '7190',  # Other non-operating revenues
                     '7200', '7210', '7220', '7230', '7240', '7250', '7260', '7270', '7280', '7290',  # Transfers in
                     '7300', '7310', '7320', '7330', '7340', '7350', '7360', '7370', '7380', '7390',  # Other financing sources
                     '7400', '7410', '7420', '7430', '7440', '7450', '7460', '7470', '7480', '7490',  # Proceeds from debt
                     '7500', '7510', '7520', '7530', '7540', '7550', '7560', '7570', '7580', '7590',  # Proceeds from sale of assets
                     '7600', '7610', '7620', '7630', '7640', '7650', '7660', '7670', '7680', '7690',  # Other sources
                     '7700', '7710', '7720', '7730', '7740', '7750', '7760', '7770', '7780', '7790',  # Special items
                     '7800', '7810', '7820', '7830', '7840', '7850', '7860', '7870', '7880', '7890',  # Extraordinary items
                     '7900', '7910', '7915', '7920', '7930', '7940', '7950', '7960', '7970', '7980', '7990']  # Other resources
    },
    'other_uses': {
        'description': 'Other Uses & Non-operating Expenses',
        'tea_codes': ['8000', '8010', '8020', '8030', '8040', '8050', '8060', '8070', '8080', '8090',  # Interest expense
                     '8100', '8110', '8120', '8130', '8140', '8150', '8160', '8170', '8180', '8190',  # Other non-operating expenses
                     '8200', '8210', '8220', '8230', '8240', '8250', '8260', '8270', '8280', '8290',  # Transfers out
                     '8300', '8310', '8320', '8330', '8340', '8350', '8360', '8370', '8380', '8390',  # Other financing uses
                     '8400', '8410', '8420', '8430', '8440', '8450', '8460', '8470', '8480', '8490',  # Principal payments on debt
                     '8500', '8510', '8520', '8530', '8540', '8550', '8560', '8570', '8580', '8590',  # Purchase of assets
                     '8600', '8610', '8620', '8630', '8640', '8650', '8660', '8670', '8680', '8690',  # Other uses
                     '8700', '8710', '8720', '8730', '8740', '8750', '8760', '8770', '8780', '8790',  # Special items
                     '8800', '8810', '8820', '8830', '8840', '8850', '8860', '8870', '8880', '8890',  # Extraordinary items
                     '8900', '8910', '8920', '8930', '8940', '8950', '8960', '8970', '8980', '8990']  # Other uses
    },
    
    # Clearing Accounts
    'clearing_accounts': {
        'description': 'Clearing Accounts',
        'tea_codes': ['4000', '4010', '4020', '4030', '4040', '4050', '4060', '4070', '4080', '4090',  # General clearing
                     '4100', '4110', '4120', '4130', '4140', '4150', '4160', '4170', '4180', '4190',  # Interfund clearing
                     '4200', '4210', '4220', '4230', '4240', '4250', '4260', '4270', '4280', '4290',  # Other clearing
                     '4300', '4310', '4320', '4330', '4340', '4350', '4360', '4370', '4380', '4390',  # Suspense clearing
                     '4400', '4410', '4420', '4430', '4440', '4450', '4460', '4470', '4480', '4490',  # Temporary clearing
                     '4500', '4510', '4520', '4530', '4540', '4550', '4560', '4570', '4580', '4590',  # Adjustment clearing
                     '4600', '4610', '4620', '4630', '4640', '4650', '4660', '4670', '4680', '4690',  # Reclassification clearing
                     '4700', '4710', '4720', '4730', '4740', '4750', '4760', '4770', '4780', '4790',  # Closing clearing
                     '4800', '4810', '4820', '4830', '4840', '4850', '4860', '4870', '4880', '4890',  # Opening clearing
                     '4900', '4910', '4920', '4930', '4940', '4950', '4960', '4970', '4980', '4990']  # Other clearing accounts
    }
}

# Fund Categories for Governmental Funds
FUND_CATEGORIES = {
    'general_fund': {
        'description': 'General Fund',
        'fund_codes': ['100', '101', '102', '103', '104', '105', '106', '107', '108', '109',
                      '110', '111', '112', '113', '114', '115', '116', '117', '118', '119',
                      '120', '121', '122', '123', '124', '125', '126', '127', '128', '129',
                      '130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
                      '140', '141', '142', '143', '144', '145', '146', '147', '148', '149',
                      '150', '151', '152', '153', '154', '155', '156', '157', '158', '159',
                      '160', '161', '162', '163', '164', '165', '166', '167', '168', '169',
                      '170', '171', '172', '173', '174', '175', '176', '177', '178', '179',
                      '180', '181', '182', '183', '184', '185', '186', '187', '188', '189',
                      '190', '191', '192', '193', '194', '195', '196', '197', '198', '199']
    },
    'special_revenue_funds': {
        'description': 'Special Revenue Funds',
        'fund_codes': ['200', '201', '202', '203', '204', '205', '206', '207', '208', '209',
                      '210', '211', '212', '213', '214', '215', '216', '217', '218', '219',
                      '220', '221', '222', '223', '224', '225', '226', '227', '228', '229',
                      '230', '231', '232', '233', '234', '235', '236', '237', '238', '239',
                      '240', '241', '242', '243', '244', '245', '246', '247', '248', '249',
                      '250', '251', '252', '253', '254', '255', '256', '257', '258', '259',
                      '260', '261', '262', '263', '264', '265', '266', '267', '268', '269',
                      '270', '271', '272', '273', '274', '275', '276', '277', '278', '279',
                      '280', '281', '282', '283', '284', '285', '286', '287', '288', '289',
                      '290', '291', '292', '293', '294', '295', '296', '297', '298', '299']
    },
    'enterprise_funds': {
        'description': 'Enterprise Funds',
        'fund_codes': ['300', '301', '302', '303', '304', '305', '306', '307', '308', '309',
                      '310', '311', '312', '313', '314', '315', '316', '317', '318', '319',
                      '320', '321', '322', '323', '324', '325', '326', '327', '328', '329',
                      '330', '331', '332', '333', '334', '335', '336', '337', '338', '339',
                      '340', '341', '342', '343', '344', '345', '346', '347', '348', '349',
                      '350', '351', '352', '353', '354', '355', '356', '357', '358', '359',
                      '360', '361', '362', '363', '364', '365', '366', '367', '368', '369',
                      '370', '371', '372', '373', '374', '375', '376', '377', '378', '379',
                      '380', '381', '382', '383', '384', '385', '386', '387', '388', '389',
                      '390', '391', '392', '393', '394', '395', '396', '397', '398', '399']
    },
    'internal_service_funds': {
        'description': 'Internal Service Funds',
        'fund_codes': ['400', '401', '402', '403', '404', '405', '406', '407', '408', '409',
                      '410', '411', '412', '413', '414', '415', '416', '417', '418', '419',
                      '420', '421', '422', '423', '424', '425', '426', '427', '428', '429',
                      '430', '431', '432', '433', '434', '435', '436', '437', '438', '439',
                      '440', '441', '442', '443', '444', '445', '446', '447', '448', '449',
                      '450', '451', '452', '453', '454', '455', '456', '457', '458', '459',
                      '460', '461', '462', '463', '464', '465', '466', '467', '468', '469',
                      '470', '471', '472', '473', '474', '475', '476', '477', '478', '479',
                      '480', '481', '482', '483', '484', '485', '486', '487', '488', '489',
                      '490', '491', '492', '493', '494', '495', '496', '497', '498', '499']
    },
    'debt_service_funds': {
        'description': 'Debt Service Funds',
        'fund_codes': ['500', '501', '502', '503', '504', '505', '506', '507', '508', '509',
                      '510', '511', '512', '513', '514', '515', '516', '517', '518', '519',
                      '520', '521', '522', '523', '524', '525', '526', '527', '528', '529',
                      '530', '531', '532', '533', '534', '535', '536', '537', '538', '539',
                      '540', '541', '542', '543', '544', '545', '546', '547', '548', '549',
                      '550', '551', '552', '553', '554', '555', '556', '557', '558', '559',
                      '560', '561', '562', '563', '564', '565', '566', '567', '568', '569',
                      '570', '571', '572', '573', '574', '575', '576', '577', '578', '579',
                      '580', '581', '582', '583', '584', '585', '586', '587', '588', '589',
                      '590', '591', '592', '593', '594', '595', '596', '597', '598', '599']
    },
    'capital_projects_funds': {
        'description': 'Capital Projects Funds',
        'fund_codes': ['600', '601', '602', '603', '604', '605', '606', '607', '608', '609',
                      '610', '611', '612', '613', '614', '615', '616', '617', '618', '619',
                      '620', '621', '622', '623', '624', '625', '626', '627', '628', '629',
                      '630', '631', '632', '633', '634', '635', '636', '637', '638', '639',
                      '640', '641', '642', '643', '644', '645', '646', '647', '648', '649',
                      '650', '651', '652', '653', '654', '655', '656', '657', '658', '659',
                      '660', '661', '662', '663', '664', '665', '666', '667', '668', '669',
                      '670', '671', '672', '673', '674', '675', '676', '677', '678', '679',
                      '680', '681', '682', '683', '684', '685', '686', '687', '688', '689',
                      '690', '691', '692', '693', '694', '695', '696', '697', '698', '699']
    },
    'permanent_funds': {
        'description': 'Permanent Funds',
        'fund_codes': ['700', '701', '702', '703', '704', '705', '706', '707', '708', '709',
                      '710', '711', '712', '713', '714', '715', '716', '717', '718', '719',
                      '720', '721', '722', '723', '724', '725', '726', '727', '728', '729',
                      '730', '731', '732', '733', '734', '735', '736', '737', '738', '739',
                      '740', '741', '742', '743', '744', '745', '746', '747', '748', '749',
                      '750', '751', '752', '753', '754', '755', '756', '757', '758', '759',
                      '760', '761', '762', '763', '764', '765', '766', '767', '768', '769',
                      '770', '771', '772', '773', '774', '775', '776', '777', '778', '779',
                      '780', '781', '782', '783', '784', '785', '786', '787', '788', '789',
                      '790', '791', '792', '793', '794', '795', '796', '797', '798', '799']
    },
    'fiduciary_funds': {
        'description': 'Fiduciary Funds',
        'fund_codes': ['800', '801', '802', '803', '804', '805', '806', '807', '808', '809',
                      '810', '811', '812', '813', '814', '815', '816', '817', '818', '819',
                      '820', '821', '822', '823', '824', '825', '826', '827', '828', '829',
                      '830', '831', '832', '833', '834', '835', '836', '837', '838', '839',
                      '840', '841', '842', '843', '844', '845', '846', '847', '848', '849',
                      '850', '851', '852', '853', '854', '855', '856', '857', '858', '859',
                      '860', '861', '862', '863', '864', '865', '866', '867', '868', '869',
                      '870', '871', '872', '873', '874', '875', '876', '877', '878', '879',
                      '880', '881', '882', '883', '884', '885', '886', '887', '888', '889',
                      '890', '891', '892', '893', '894', '895', '896', '897', '898', '899']
    }
}

# Fund Categories for Governmental Funds
# FUND_CATEGORIES = {
#     'general_fund': {
#         'description': 'General Fund',
#         'fund_codes': ['100', '101', '102', '103', '104', '105', '106', '107', '108', '109',
#                       '110', '111', '112', '113', '114', '115', '116', '117', '118', '119',
#                       '120', '121', '122', '123', '124', '125', '126', '127', '128', '129',
#                       '130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
#                       '140', '141', '142', '143', '144', '145', '146', '147', '148', '149',
#                       '150', '151', '152', '153', '154', '155', '156', '157', '158', '159',
#                       '160', '161', '162', '163', '164', '165', '166', '167', '168', '169',
#                       '170', '171', '172', '173', '174', '175', '176', '177', '178', '179',
#                       '180', '181', '182', '183', '184', '185', '186', '187', '188', '189',
#                       '190', '191', '192', '193', '194', '195', '196', '197', '198', '199']
#     },
#     'special_revenue_funds': {
#         'description': 'Special Revenue Funds',
#         'fund_codes': ['200', '201', '202', '203', '204', '205', '206', '207', '208', '209',
#                       '210', '211', '212', '213', '214', '215', '216', '217', '218', '219',
#                       '220', '221', '222', '223', '224', '225', '226', '227', '228', '229',
#                       '230', '231', '232', '233', '234', '235', '236', '237', '238', '239',
#                       '240', '241', '242', '243', '244', '245', '246', '247', '248', '249',
#                       '250', '251', '252', '253', '254', '255', '256', '257', '258', '259',
#                       '260', '261', '262', '263', '264', '265', '266', '267', '268', '269',
#                       '270', '271', '272', '273', '274', '275', '276', '277', '278', '279',
#                       '280', '281', '282', '283', '284', '285', '286', '287', '288', '289',
#                       '290', '291', '292', '293', '294', '295', '296', '297', '298', '299']
#     },
#     'debt_service_funds': {
#         'description': 'Debt Service Funds',
#         'fund_codes': ['500', '501', '502', '503', '504', '505', '506', '507', '508', '509']
#     },
#     'capital_projects_funds': {
#         'description': 'Capital Projects Funds',
#         'fund_codes': ['600', '601', '602', '603', '604', '605', '606', '607', '608', '609']
#     },
#     'permanent_funds': {
#         'description': 'Permanent Funds',
#         'fund_codes': ['700', '701', '702', '703', '704', '705', '706', '707', '708', '709']
#     }
# }

def get_tea_category(account_code):
    """Get TEA category based on account code"""
    if len(account_code) >= 9:  # Need at least 9 digits for object code
        first_digit = account_code[5]  # Object code starts at position 5 (0-indexed)
        return TEA_OBJECT_CATEGORIES.get(first_digit, 'Unknown')
    return 'Unknown'

def get_gasb_category(account_code):
    """Get GASB category based on account code using pattern matching"""
    if len(account_code) >= 9:  # Need at least 9 digits for object code
        object_code = account_code[5:9]  # Extract 4-digit object code (positions 5-8)
        
        # First try exact matches in the predefined categories
        for category, details in GASB_CATEGORIES.items():
            if object_code in details['tea_codes']:
                return category
        
        # Pattern matching fallback for comprehensive coverage
        if object_code.startswith('1'):  # All assets (1000-1999)
            if object_code.startswith(('11', '12', '13', '14')):  # Current assets (1100-1499)
                return 'current_assets'
            elif object_code.startswith('15'):  # Capital assets (1500-1599)
                return 'capital_assets'
            elif object_code.startswith('17'):  # Deferred outflows (1700-1799)
                return 'deferred_outflows'
            else:
                return 'current_assets'  # Default to current assets for other 1XXX codes
                
        elif object_code.startswith('2'):  # All liabilities (2000-2999)
            if object_code.startswith(('21', '22', '23')):  # Current liabilities (2100-2399)
                return 'current_liabilities'
            elif object_code.startswith(('24', '25')):  # Long-term liabilities (2400-2599)
                return 'long_term_liabilities'
            elif object_code.startswith('26'):  # Deferred inflows (2600-2699)
                return 'deferred_inflows'
            else:
                return 'current_liabilities'  # Default to current liabilities for other 2XXX codes
                
        elif object_code.startswith('3'):  # All net position (3000-3999)
            if object_code.startswith('32'):  # Net investment in capital assets (3200-3299)
                return 'net_investment_capital_assets'
            elif object_code.startswith(('33', '34', '35', '36', '37', '38')):  # Restricted net position (3300-3899)
                return 'restricted_net_position'
            elif object_code.startswith('39'):  # Unrestricted net position (3900-3999)
                return 'unrestricted_net_position'
            else:
                return 'restricted_net_position'  # Default to restricted for other 3XXX codes
                
        elif object_code.startswith('5'):  # All revenues (5000-5999)
            if object_code.startswith(('51', '52', '53')):  # Program revenues (5100-5399)
                return 'program_revenues'
            else:  # General revenues (5400-5999)
                return 'general_revenues'
                
        elif object_code.startswith('6'):  # All expenses (6000-6999)
            if object_code.startswith(('61', '62', '63', '64', '65')):  # Program expenses (6100-6599)
                return 'program_expenses'
            else:  # General expenses (6600-6999)
                return 'general_expenses'
                
        elif object_code.startswith('7'):  # Other resources/non-operating revenues (7000-7999)
            return 'other_resources'
            
        elif object_code.startswith('8'):  # Other uses/non-operating expenses (8000-8999)
            return 'other_uses'
    
    return 'unknown'

def get_fund_category(account_code):
    """Get fund category based on account code using pattern matching"""
    if len(account_code) >= 3:
        fund_code = account_code[0:3]  # First 3 digits are fund code
        
        # First try exact matches in the predefined categories
        for category, details in FUND_CATEGORIES.items():
            if fund_code in details['fund_codes']:
                return category
        
        # Pattern matching fallback for comprehensive coverage
        if fund_code.startswith('1'):  # General Fund (100-199)
            return 'general_fund'
        elif fund_code.startswith('2'):  # Special Revenue Funds (200-299)
            return 'special_revenue_funds'
        elif fund_code.startswith('5'):  # Debt Service Funds (500-599)
            return 'debt_service_funds'
        elif fund_code.startswith('6'):  # Capital Projects Funds (600-699)
            return 'capital_projects_funds'
        elif fund_code.startswith('7'):  # Permanent Funds (700-799)
            return 'permanent_funds'
        else:
            return 'other_governmental_funds'  # Default for other fund codes
    
    return 'other_governmental_funds'

def create_default_mapping(account_codes):
    """Create default mapping for a list of account codes"""
    mapping = {}
    
    for code in account_codes:
        mapping[code] = {
            'account_code': code,
            'description': f'Account {code}',
            'tea_category': get_tea_category(code),
            'gasb_category': get_gasb_category(code),
            'fund_category': get_fund_category(code),
            'statement_line': 'XX',  # To be determined during statement generation
            'notes': ''
        }
    
    return mapping

def validate_account_code(account_code):
    """Validate TEA account code format and extract components"""
    if len(account_code) < 9:
        return False, "Account code too short (minimum 9 digits required)"
    
    try:
        fund_code = account_code[0:3]
        function_code = account_code[3:5]
        object_code = account_code[5:9]
        
        # Basic validation
        if not fund_code.isdigit() or not function_code.isdigit() or not object_code.isdigit():
            return False, "Account code contains non-numeric characters"
        
        return True, {
            'fund_code': fund_code,
            'function_code': function_code,
            'object_code': object_code,
            'full_code': account_code
        }
    except Exception as e:
        return False, f"Error parsing account code: {str(e)}"

def get_account_components(account_code):
    """Extract and return all components of a TEA account code"""
    is_valid, result = validate_account_code(account_code)
    if is_valid:
        return result
    else:
        return {
            'fund_code': '000',
            'function_code': '00', 
            'object_code': '0000',
            'full_code': account_code,
            'error': result
        }

def validate_mapping(mapping):
    """Validate that mapping covers the accounts that need mapping"""
    mapped_categories = set()
    unmapped_accounts = []
    invalid_accounts = []
    
    for account_code, account_mapping in mapping.items():
        # Validate account code format
        is_valid, _ = validate_account_code(account_code)
        if not is_valid:
            invalid_accounts.append(account_code)
            continue
            
        if account_mapping.get('gasb_category') and account_mapping.get('gasb_category') != 'unknown':
            mapped_categories.add(account_mapping['gasb_category'])
        else:
            unmapped_accounts.append(account_code)
    
    # Check if we have a good distribution of categories for financial statements
    essential_categories = {
        'assets': ['current_assets', 'capital_assets'],
        'liabilities': ['current_liabilities', 'long_term_liabilities'],
        'net_position': ['net_investment_capital_assets', 'restricted_net_position', 'unrestricted_net_position'],
        'revenues': ['program_revenues', 'general_revenues'],
        'expenses': ['program_expenses', 'general_expenses']
    }
    
    warnings = []
    for category_group, categories in essential_categories.items():
        if not any(cat in mapped_categories for cat in categories):
            warnings.append(f"No {category_group.replace('_', ' ')} categories mapped")
    
    return {
        'valid': len(unmapped_accounts) == 0 and len(invalid_accounts) == 0,
        'unmapped_accounts': unmapped_accounts[:10],  # Show first 10 unmapped accounts
        'invalid_accounts': invalid_accounts[:10],  # Show first 10 invalid accounts
        'total_unmapped': len(unmapped_accounts),
        'total_invalid': len(invalid_accounts),
        'mapped_categories': list(mapped_categories),
        'warnings': warnings,
        'has_essential_categories': len(warnings) == 0
    }
