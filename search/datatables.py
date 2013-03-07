'''
Created on Apr 18, 2011
@author: Russell Wong
http://rus.hk/django-data-parser-for-jquery-datatable/
'''
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.cache import add_never_cache_headers
import json
 
# To datatablize fields
def datatablize_fields(fields):
    mapped_fields = dict()
    for idx, value in enumerate(fields):
        mapped_fields[idx] = value
    return mapped_fields
 
# To datatablize queryset
def datatablize(request, querySet, fields, jsonTemplatePath=None, *args):
 
    """
    Usage:
        querySet: query set to draw data from.
        mapped_fields: field names in order to be displayed.
        jsonTemplatePath: optional template file to generate custom json from.  If not provided it will generate the data directly from the model.
    """
 
    if not isinstance(fields, dict):
        mapped_fields = datatablize_fields(fields)
    else:
        mapped_fields = fields
 
    # Get the number of columns
    cols = int(request.GET.get('iColumns', 0))
    # Safety measure. If someone messes with iDisplayLength manually, we clip it to the max value of 100.
    iDisplayLength = min(int(request.GET.get('iDisplayLength', 10)), 100)
    # Where the data starts from (page)
    startRecord = int(request.GET.get('iDisplayStart', 0))
    # where the data ends (end of page)
    endRecord = startRecord + iDisplayLength 
 
    # Pass sColumns
    keys = mapped_fields.keys()
    keys.sort()
    colitems = [mapped_fields[key] for key in keys]
    sColumns = ",".join(map(str, colitems))
 
    # Ordering data
    iSortingCols = int(request.GET.get('iSortingCols', 0))
    asortingCols = []
 
    if iSortingCols:
        for sortedColIndex in range(0, iSortingCols):
            sortedColID = int(request.GET.get('iSortCol_' + str(sortedColIndex), 0))
            if request.GET.get('bSortable_{0}'.format(sortedColID), 'false') == 'true':  # make sure the column is sortable first
                sortedColName = mapped_fields[sortedColID]
                sortingDirection = request.GET.get('sSortDir_' + str(sortedColIndex), 'asc')
                if sortingDirection == 'desc':
                    sortedColName = '-' + sortedColName
                asortingCols.append(sortedColName)
        querySet = querySet.order_by(*asortingCols)
 
    # Determine which columns are searchable
    searchableColumns = []
    for col in range(0, cols):
        if request.GET.get('bSearchable_{0}'.format(col), False) == 'true': searchableColumns.append(mapped_fields[col])
 
    # Apply filtering with sSearch value
    customSearch = request.GET.get('sSearch', '').encode('utf-8');
    if customSearch != '':
        outputQ = None
        first = True
        for searchableColumn in searchableColumns:
            kwargz = {searchableColumn + "__icontains" : customSearch}
            outputQ = outputQ | Q(**kwargz) if outputQ else Q(**kwargz)
        querySet = querySet.filter(outputQ)
 
    # Individual column search
    outputQ = None
    for col in range(0, cols):
        if request.GET.get('sSearch_{0}'.format(col), False) > '' and request.GET.get('bSearchable_{0}'.format(col), False) == 'true':
            kwargz = {mapped_fields[col] + "__icontains" : request.GET['sSearch_{0}'.format(col)]}
            outputQ = outputQ & Q(**kwargz) if outputQ else Q(**kwargz)
    if outputQ: querySet = querySet.filter(outputQ)
    # count how many records match the final criteria
    iTotalRecords = iTotalDisplayRecords = querySet.count()
    # get the slice
    querySet = querySet[startRecord:endRecord]
    # required echo response
    sEcho = int(request.GET.get('sEcho', 0))
    if jsonTemplatePath:
        # prepare the JSON with the response, consider using : from django.template.defaultfilters import escapejs
        jstonString = render_to_string(jsonTemplatePath, locals())
        response = HttpResponse(jstonString, mimetype="application/javascript")
    else:
        aaData = list(querySet.values_list(*[ col for col in mapped_fields.values()]))
        response_dict = {}
        response_dict.update({'aaData':aaData})
        response_dict.update({'sEcho': sEcho, 'iTotalRecords': iTotalRecords, 'iTotalDisplayRecords':iTotalDisplayRecords, 'sColumns':sColumns})
        response = HttpResponse(json.dumps(response_dict, cls=DjangoJSONEncoder), mimetype='application/javascript')
 
    #prevent from caching datatables result
    add_never_cache_headers(response)
    return response
