# SPDX-License-Identifier: MIT
"""Source-reviewed biology scripts and connected educational scene assemblies."""
import re

from mechanism_animation import read_mechanism


BIOLOGY_REFERENCES = {
    'oral-medicine':('NIH: What happens to medicine in your body',
                    'https://www.nigms.nih.gov/biobeat/2023/09/what-happens-to-medicine-in-your-body'),
    'swallowing-peristalsis':('NIDDK: Your digestive system and how it works',
                             'https://www.niddk.nih.gov/health-information/digestive-diseases/digestive-system-how-it-works'),
    'alveolar-gas-exchange':('NHLBI: How the lungs work','https://www.nhlbi.nih.gov/health/lungs'),
}


def biology_topic(prompt):
    text=prompt.casefold()
    if re.search(r'\b(?:pills?|tablets?|capsules?|oral medic(?:ine|ation))\b',text):
        # A general immediate-release journey cannot stand in for a named drug,
        # modified-release product, local treatment, or manufacturing mechanism.
        if not re.search(r'\b(?:enteric|extended[- ]release|controlled[- ]release|delayed[- ]release|sublingual|'
                         r'ibuprofen|aspirin|paracetamol|acetaminophen|antibiotic|insulin|opioid|chemotherapy|'
                         r'manufactur\w*|tablet press|capsule filling|topical)\b',text):
            return 'oral-medicine'
    if re.search(r'\b(?:alveol\w*|gas exchange|lungs?\b.*\boxygen|oxygen\b.*\blungs?)\b',text):
        return 'alveolar-gas-exchange'
    if re.search(r'\b(?:peristalsis|swallowing|esophagus|oesophagus)\b',text) and not re.search(r'\b(?:colon|large intestine|small intestine)\b',text):
        return 'swallowing-peristalsis'
    return None


def biology_storyboard(topic,max_seconds=60,dosage_form='tablet'):
    short=max_seconds==25
    if topic=='oral-medicine':
        title='What Happens After You Swallow a Tablet?'
        hook='Where does a swallowed tablet go?'
        steps=[
            ('Swallow and transport','Swallowing sends the tablet into the esophagus. A coordinated muscle wave pushes it toward the stomach.',
             'The esophagus pushes the swallowed tablet toward the stomach.'),
            ('Break apart and dissolve','Here, an immediate-release tablet can break apart. Active ingredients dissolve in digestive fluid; the solid tablet does not enter blood.',
             'An immediate-release tablet breaks apart; its active ingredient dissolves.'),
            ('Cross the intestinal lining','In the small intestine, dissolved medicine crosses the lining. Enlarged villi show the large surface available for absorption.',
             'Dissolved medicine crosses the small-intestine lining into blood.'),
            ('Pass through the liver','Portal blood carries absorbed medicine to the liver. Enzymes may change some of it before it reaches systemic circulation.',
             'Portal blood carries it through the liver before systemic circulation.'),
            ('Reach a target','Circulating molecules reach tissues. Some medicines bind to specific proteins and change cell activity; other medicines work differently.',
             'Some medicines bind to target proteins and change cell activity.'),
            ('Process and remove','The liver changes many medicines, and kidneys remove many drugs or metabolites. Timing varies by medicine and formulation.',
             'The body processes and removes medicine. Each drug behaves differently.'),
        ]
        description=('An illustrative immediate-release oral medicine journey: swallowing, disintegration and dissolution, intestinal absorption, portal blood and liver processing, circulation, example protein binding and clearance. '
                     'The binding example does not describe every medicine. Particle size, anatomy and timing are schematic; no dose or treatment recommendation is shown.')
    elif topic=='swallowing-peristalsis':
        title='How Swallowing Moves Food Without Gravity'
        hook='What pushes food down your esophagus?'
        steps=[
            ('Enter the esophagus','After swallowing, the food bolus enters the esophagus, the muscular tube connecting the throat to the stomach. The airway is a separate passage.',
             'The swallowed food bolus enters the muscular esophagus.'),
            ('Squeeze behind the bolus','Circular muscle contracts behind the bolus. Ahead of it, the tube relaxes. This difference pushes the food forward rather than simply letting it fall.',
             'Muscle squeezes behind the bolus while the tube ahead relaxes.'),
            ('Travel as a wave','The contraction progresses along the tube. The food travels with the moving wave, while the section behind it returns toward its resting diameter.',
             'The moving contraction pushes food along the tube.'),
            ('Approach the stomach','The coordinated wave continues toward the stomach. This muscular transport is called peristalsis. It does not depend on gravity alone to move swallowed food.',
             'Peristalsis continues toward the stomach without relying on gravity alone.'),
            ('Enter and relax','The lower esophageal sphincter relaxes to let the bolus enter the stomach, then normally closes. The esophagus relaxes after the food has passed through.',
             'The lower sphincter opens for the bolus, then normally closes.'),
        ]
        description='A connected esophagus cutaway follows one food bolus and the contraction behind it. Muscle rings visibly narrow and relax as the bolus progresses toward the stomach. Schematic anatomy and accelerated timing.'
    elif topic=='alveolar-gas-exchange':
        title='How Oxygen Gets From Your Lungs Into Blood'
        hook='How does a breath reach your blood?'
        steps=[
            ('Bring air to the alveoli','Breathing in brings fresh air through branching airways to tiny air sacs called alveoli. Their thin walls sit close to a network of blood capillaries.',
             'Fresh air reaches tiny air sacs called alveoli.'),
            ('Oxygen crosses the barrier','Oxygen moves from the alveolar air across the thin air-blood barrier into the blood. This diffusion follows a difference in oxygen partial pressure across the barrier.',
             'Oxygen diffuses across the thin wall from air into blood.'),
            ('Carry oxygen in blood','Inside red blood cells, hemoglobin binds most of the oxygen carried in blood. Flowing blood then transports that oxygen away from the lungs toward the body.',
             'Red blood cells carry oxygen away, mostly bound to hemoglobin.'),
            ('Move carbon dioxide out','Carbon dioxide moves in the opposite direction, from blood into the alveolar air. Oxygen entry and carbon dioxide removal happen together across the same thin exchange region.',
             'Carbon dioxide moves from blood into the alveolar air.'),
            ('Breathe out and repeat','Breathing out removes air containing carbon dioxide. The next breath brings fresh air, while blood continues flowing past the alveoli. Ventilation and circulation maintain gas exchange.',
             'Breathing out removes carbon dioxide; fresh air renews the cycle.'),
        ]
        description='A breathing lung and alveolar-capillary cutaway with moving biconcave red blood cells. Cyan markers represent oxygen, amber markers carbon dioxide; markers are enlarged and transfer rates are illustrative.'
    else:
        raise ValueError('Unknown reviewed biology scene')
    reference,url=BIOLOGY_REFERENCES[topic]
    if topic=='oral-medicine' and dosage_form=='capsule':
        title=title.replace('Tablet','Capsule');hook=hook.replace('tablet','capsule')
        steps=[tuple(text.replace('tablet','capsule') for text in step) for step in steps]
        description=description.replace('tablet','capsule')
    return {'template':topic,'title':title,'hook':hook,'hook_view':'wide',
            'description':description+' Reference: '+url,
            'hashtags':['#Biology','#HowItWorks','#Science','#Shorts'],
            'scenes':[{'heading':heading,'view':'wide','narration':brief if short else narration,'caption':heading+'.'}
                      for heading,narration,brief in steps]}


def biology_mechanism(topic,beats,dosage_form='tablet'):
    parts=[];actions=[]
    def part(name,shape,points,color='tissue'):
        x,y=zip(*points)
        parts.append(dict(name=name,shape=shape,color=color,points=points,pivot=[(min(x)+max(x))/2,(min(y)+max(y))/2]))
    def action(beat,name,effect,x,y=0,start=.05,end=.90):
        actions.append(dict(beat=beat,part=name,effect=effect,amount=[x,y],start=start,end=end))
    if topic=='oral-medicine':
        if beats!=7:
            raise ValueError('The medicine journey needs its six ordered body stages')
        part('Torso','torso',[[13,8],[87,97]])
        part('Head','head',[[43,0],[67,19]])
        part('Mouth','mouth',[[51,9],[66,17]])
        part('Esophagus','esophagus',[[52,19],[58,39]])
        part('Stomach','stomach',[[49,36],[76,58]])
        part('Small intestine','intestine',[[31,59],[69,86]])
        part('Duodenum','digestive_tube',[[50,50],[48,55],[43,55],[38,60],[37.46,61.97]])
        part('Liver','liver',[[22,38],[50,53]])
        part('Heart','heart',[[37,25],[48,38]])
        part('Left kidney','kidney',[[24,64],[34,79]])
        part('Right kidney','kidney',[[75,64],[85,79]])
        part('Tablet','capsule' if dosage_form=='capsule' else 'tablet',[[63,10.5],[67,13.5]],'white')
        part('Portal blood','blood_vessel',[[49,70],[28,67],[28,49],[36,48]],'blood')
        part('Villus','villus',[[10,34],[30,69]])
        part('Absorption capillary','blood_vessel',[[11,61],[29,61]],'blood')
        part('Target cell','cell',[[12,50],[45,80]])
        part('Cell membrane','membrane',[[12,45],[45,53]])
        part('Target receptor','receptor',[[25,40],[32,57]],'purple')
        part('Left ureter','ureter',[[29,77],[33,83],[47,90]])
        part('Right ureter','ureter',[[80,77],[74,83],[56,90]])
        part('Bladder','bladder',[[46,85],[57,97]])
        action(1,'Tablet','move',-10,27)
        action(2,'Tablet','move',7,8,start=0,end=.18)
        action(2,'Tablet','dissolve',1,start=.18,end=.88)
        action(3,'Absorption capillary','flow',1)
        action(4,'Portal blood','flow',1)
        action(5,'Heart','pulse',1,.04)
        action(6,'Portal blood','flow',1)
    elif topic=='swallowing-peristalsis':
        if beats!=6:
            raise ValueError('The swallowing cycle needs five body stages')
        part('Esophagus','esophagus',[[42,13],[58,87]])
        part('Food bolus','food_bolus',[[45,18],[55,29]])
        part('Stomach','stomach',[[46,84],[81,99]])
        for beat,distance in ((1,10),(2,15),(3,17),(4,14)):
            action(beat,'Food bolus','move',0,distance)
        action(5,'Food bolus','move',10,10)
    elif topic=='alveolar-gas-exchange':
        if beats!=6:
            raise ValueError('The gas-exchange cycle needs five body stages')
        part('Lungs','lung',[[22,10],[78,43]])
        part('Alveoli','alveolus',[[26,46],[73,84]])
        part('Blood capillary','blood_vessel',[[16,74],[21,57],[33,46],[60,47],[80,63],[87,80]],'blood')
        action(1,'Lungs','pulse',.18,.045)
        action(2,'Alveoli','pulse',.18,.035)
        for beat in (1,2,3,4,5):
            action(beat,'Blood capillary','flow',1,start=0,end=1)
    else:
        raise ValueError('Unknown reviewed biology scene')
    return read_mechanism({'parts':parts,'actions':actions},beats)
