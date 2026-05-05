import pytest

from pycldf import Dataset

from pyglottolog.links import wikidata
from pyglottolog.links.util import LinkProvider

CLDF_MD = """\
{
  "@context": ["http://www.w3.org/ns/csvw", {"@language": "en"}],
  "dc:conformsTo": "http://cldf.clld.org/v1.0/terms.rdf#Generic",
  "tables": [
    {
      "dc:conformsTo": "http://cldf.clld.org/v1.0/terms.rdf#LanguageTable",
      "tableSchema": {
        "columns": [
          {
            "datatype": {"base": "string"},
            "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#id",
            "required": true,
            "name": "ID"
          },
          {
            "datatype": "string",
            "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#name",
            "required": false,
            "name": "Name"
          },
          {
            "datatype": "string",
            "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#glottocode",
            "name": "Glottocode"
          }
        ],
        "primaryKey": ["ID"]
      },
      "url": "languages.csv"
    }
  ]
}"""



def test_wikidata(mocker, api_copy):
    langs = {l.id: l for l in api_copy.languoids()}
    with pytest.raises(AssertionError):
        _ = list(wikidata.Wikidata().iterupdated(langs.values()))


def test_LinkProvider(mocker, api):
    def download_dataset(d):
        d.joinpath('cldf.json').write_text(CLDF_MD, encoding='utf8')
        d.joinpath('languages.csv').write_text("ID,Name,Glottocode\na,Alanguage,abcd1234")
        return Dataset.from_metadata(d.joinpath('cldf.json'))

    class Api(mocker.Mock):
        def get_record(self, *_, **kw):
            return mocker.Mock(download_dataset=download_dataset)

    class TestLinks(LinkProvider):
        __doi__ = 'x'
        __domain__ = 'y'
        __url_template__ = "{0[ID]}"
        __label_template__ = "{0[Name]}"

    mocker.patch('pyglottolog.links.util.cldfzenodo', mocker.Mock(API=Api()))

    l = TestLinks()
    res = list(l.iterupdated(api.languoids()))
    assert len(res) == 1
    assert res[0].links[0].url == 'a'
    assert res[0].links[0].label == 'Alanguage'
